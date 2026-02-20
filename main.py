import io
import re
import aiohttp
import asyncio
import uuid
import ipaddress
from urllib.parse import urlparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
# 移除了未使用的 Plain 导入
from astrbot.api.message_components import Image as AstrImage, At

# 统一工作尺寸
WORK_WIDTH = 1000
WORK_HEIGHT = 1000

# 安全限制配置
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB 最大体积限制
Image.MAX_IMAGE_PIXELS = 15000000 # 约 1500 万像素上限，防解压炸弹

@register("aisharelogo", "工一阵", "制作分钱logo", "1.0")
class AILogoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 1. 插件源码自带目录
        self.plugin_dir = Path(__file__).parent
        self.plugin_font_dir = self.plugin_dir / "font"
        self.plugin_logo_dir = self.plugin_dir / "logo"
        
        # 2. 用户数据标准目录
        self.data_dir = StarTools.get_data_dir("ailogo")
        self.data_font_dir = self.data_dir / "font"
        self.data_logo_dir = self.data_dir / "logo"
        
        # [鲁棒性提升] 异常处理：防止在只读文件系统中启动崩溃
        try:
            self.plugin_font_dir.mkdir(parents=True, exist_ok=True)
            self.plugin_logo_dir.mkdir(parents=True, exist_ok=True)
            self.data_font_dir.mkdir(parents=True, exist_ok=True)
            self.data_logo_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"ailogo 目录创建失败，请检查文件系统权限: {e}")

    # ================= 安全校验工具 =================
    
    def is_safe_url(self, url: str) -> bool:
        """基础 SSRF 防护：校验协议与内网 IP 阻断"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            # 尝试拦截直接输入内网 IP 的请求 (如 127.0.0.1, 192.168.x.x)
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback:
                    return False
            except ValueError:
                pass # 域名形式，由 aiohttp 处理
            return True
        except Exception:
            return False

    # ================= 资源寻址工具 =================

    def get_asset_path(self, filename: str, asset_type: str) -> Path | None: # [规范] 准确的类型标注
        if not filename:
            return None
            
        data_path = self.data_font_dir if asset_type == "font" else self.data_logo_dir
        plugin_path = self.plugin_font_dir if asset_type == "font" else self.plugin_logo_dir
        
        target1 = data_path / filename
        if target1.exists() and target1.is_file():
            return target1
            
        target2 = plugin_path / filename
        if target2.exists() and target2.is_file():
            return target2
            
        return None

    def get_all_assets(self, asset_type: str) -> list[str]:
        data_path = self.data_font_dir if asset_type == "font" else self.data_logo_dir
        plugin_path = self.plugin_font_dir if asset_type == "font" else self.plugin_logo_dir
        
        assets = set()
        if data_path.exists():
            assets.update(f.name for f in data_path.iterdir() if f.is_file())
        if plugin_path.exists():
            assets.update(f.name for f in plugin_path.iterdir() if f.is_file())
            
        return sorted(list(assets))

    # ================= 图像处理核心 =================

    def get_dynamic_font(self, text, font_path, target_width_ratio=0.75):
        conf_size = self.config.get("font_size", 0)
        if conf_size > 0:
            try:
                return ImageFont.truetype(str(font_path), conf_size)
            except IOError:
                return ImageFont.load_default()

        target_width = WORK_WIDTH * target_width_ratio
        font_size = 50
        max_font_size = 800
        
        try:
            font = ImageFont.truetype(str(font_path), font_size)
        except IOError:
            logger.error(f"无法加载字体 '{font_path}'。")
            return ImageFont.load_default()

        # [性能提升] 在循环外复用 Dummy 画布对象
        dummy_canvas = Image.new("RGBA", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_canvas)
        
        while font_size < max_font_size:
            bbox = dummy_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            if text_w >= target_width:
                break
            font_size += 5
            try:
                font = ImageFont.truetype(str(font_path), font_size)
            except IOError:
                break
        return font

    def draw_thick_shadow_text(self, draw, x, y, text, font, text_color, shadow_color, shadow_depth=8):
        for i in range(shadow_depth, 0, -1):
            draw.text((x + i, y + i), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=text_color)

    def process_image(self, base_image_bytes, bg_path, font_path, text_content, style_type, out_file_path):
        base_image = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")
        canvas = base_image.resize((WORK_WIDTH, WORK_HEIGHT), Image.Resampling.LANCZOS)

        bg_template = Image.open(bg_path).convert("RGBA")
        bg_template = bg_template.resize((WORK_WIDTH, WORK_HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.alpha_composite(canvas, bg_template)

        target_ratio = 0.80 if style_type == 1 else 0.75
        font = self.get_dynamic_font(text_content, font_path, target_ratio)
        
        dummy_draw = ImageDraw.Draw(canvas)
        bbox = dummy_draw.textbbox((0, 0), text_content, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        text_x = (WORK_WIDTH - text_w) // 2
        bottom_margin = 80 
        text_y = WORK_HEIGHT - text_h - bottom_margin

        if style_type == 1:
            self.draw_thick_shadow_text(
                draw=ImageDraw.Draw(canvas),
                x=text_x - bbox[0], y=text_y - bbox[1],
                text=text_content, font=font,
                text_color=(255, 248, 220), shadow_color=(160, 20, 10), shadow_depth=12             
            )
        else:
            dummy_draw.text((text_x, text_y), text_content, font=font, fill=(255, 215, 0))

        canvas.save(out_file_path, format='PNG')
        return out_file_path

    # ================= 消息链深层提取 =================
    
    def extract_image_url(self, message_chain) -> str | None:
        if not message_chain:
            return None
        for comp in message_chain:
            if isinstance(comp, AstrImage):
                return getattr(comp, "url", getattr(comp, "file", None))
            for attr in ['content', 'message', 'chain', 'components', 'nodes']:
                if hasattr(comp, attr):
                    nested = getattr(comp, attr)
                    if isinstance(nested, list):
                        res = self.extract_image_url(nested)
                        if res: return res
        return None

    # ================= 交互指令 =================

    @filter.command("lsfont")
    async def lsfont(self, event: AstrMessageEvent):
        """列出所有可用字体"""
        fonts = self.get_all_assets("font")
        if not fonts:
            yield event.plain_result("font 文件夹为空，请先放入字体文件。")
            return
        yield event.plain_result("可用字体：\n" + "\n".join(fonts))

    @filter.command("lslogo")
    async def lslogo(self, event: AstrMessageEvent):
        """列出所有可用模板"""
        logos = self.get_all_assets("logo")
        if not logos:
            yield event.plain_result("logo 文件夹为空，请先放入模板文件。")
            return
        yield event.plain_result("可用样式模板：\n" + "\n".join(logos))

    @filter.command("changefont")
    async def changefont(self, event: AstrMessageEvent, font_name: str):
        """切换默认字体，参数为字体文件名"""
        safe_font_name = Path(font_name).name
        if not self.get_asset_path(safe_font_name, "font"):
            yield event.plain_result(f"❌ 字体 {safe_font_name} 不存在于任何 font 目录中！")
            return
        self.config["default_font"] = safe_font_name
        self.config.save_config()
        yield event.plain_result(f"✅ 字体已成功切换为 {safe_font_name}")

    @filter.command("changelogo")
    async def changelogo(self, event: AstrMessageEvent, logo_name: str):
        """切换默认模板，参数为模板文件名"""
        safe_logo_name = Path(logo_name).name
        if not self.get_asset_path(safe_logo_name, "logo"):
            yield event.plain_result(f"❌ 模板 {safe_logo_name} 不存在于任何 logo 目录中！")
            return
        self.config["default_logo"] = safe_logo_name
        self.config.save_config()
        yield event.plain_result(f"✅ 模板样式已成功切换为 {safe_logo_name}")

    @filter.command("ailogo")
    async def ailogo(self, event: AstrMessageEvent):
        """主指令：生成 AI 分享 Logo 图片，支持附带图片、引用图片或 @ 群友自动获取头像。"""
        full_text = event.message_str.strip()
        parts = full_text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            text_content = parts[1].strip()
        else:
            text_content = "分10亿"

        font_file = self.config.get("default_font", "")
        logo_file = self.config.get("default_logo", "")
        
        font_path = self.get_asset_path(font_file, "font")
        bg_path = self.get_asset_path(logo_file, "logo")

        if not font_file or not font_path:
            yield event.plain_result("❌ 请先在配置面板设置 default_font 或使用 /changefont 设置有效字体。")
            return
        if not logo_file or not bg_path:
            yield event.plain_result("❌ 请先在配置面板设置 default_logo 或使用 /changelogo 设置有效模板。")
            return

        message_chain = event.get_messages()
        image_url = self.extract_image_url(message_chain)
        
        if not image_url:
            raw_msg = getattr(event.message_obj, "raw_message", {})
            raw_str = str(raw_msg)
            match = re.search(r'(https?://(?:[^/]+\.)?qpic\.cn/[^\]\'",\s]+)', raw_str)
            if not match:
                match = re.search(r'url=(https?://[^\]\'",\s]+)', raw_str)
            if match:
                image_url = match.group(1)

        if not image_url:
            target_qq = None
            for comp in message_chain:
                if isinstance(comp, At):
                    target_qq = getattr(comp, "qq", getattr(comp, "id", None))
                    break
            
            if target_qq:
                # [兼容性提升] 升级为 HTTPS
                image_url = f"https://q1.qlogo.cn/g?b=qq&nk={target_qq}&s=640"
            elif self.config.get("use_avatar_if_no_image", True):
                sender_id = event.get_sender_id()
                image_url = f"https://q1.qlogo.cn/g?b=qq&nk={sender_id}&s=640"
            else:
                yield event.plain_result("❌ 缺少图片。请在发送指令时附带图片、引用图片，或 @ 一名群友。")
                return

        yield event.plain_result("🚀 正在生成中，请稍候...")
        
        try:
            img_data = None
            if image_url.startswith("http"):
                # 安全拦截
                if not self.is_safe_url(image_url):
                    yield event.plain_result("❌ 安全拦截：不支持访问该 URL 地址。")
                    return
                
                # [稳定性提升] 增加全局超时设置
                timeout = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    # 禁止重定向，防绕过
                    async with session.get(image_url, allow_redirects=False) as resp:
                        if resp.status != 200:
                            yield event.plain_result(f"❌ 无法下载图片，网络状态码: {resp.status}")
                            return
                        
                        # [安全性提升] 头信息体积校验
                        content_length = int(resp.headers.get('Content-Length', 0))
                        if content_length > MAX_FILE_SIZE:
                            yield event.plain_result("❌ 图片文件过大，拒绝处理。")
                            return
                            
                        img_data = await resp.read()
                        
                        # 实际体积二次校验
                        if len(img_data) > MAX_FILE_SIZE:
                            yield event.plain_result("❌ 图片真实数据过大，拒绝处理。")
                            return

            else:
                # [安全性提升] 本地文件读取校验
                local_path = Path(image_url).resolve()
                if not local_path.exists() or not local_path.is_file():
                    yield event.plain_result("❌ 无法读取目标资源。")
                    return
                if local_path.stat().st_size > MAX_FILE_SIZE:
                    yield event.plain_result("❌ 本地目标文件过大，拒绝处理。")
                    return
                img_data = local_path.read_bytes()
            
            style_type = self.config.get("style_type", 1)
            temp_filename = f"temp_logo_{uuid.uuid4().hex}.png"
            temp_filepath = self.data_dir / temp_filename
            
            await asyncio.to_thread(
                self.process_image,
                img_data, str(bg_path), str(font_path), text_content, style_type, str(temp_filepath)
            )

            yield event.chain_result([AstrImage.fromFileSystem(str(temp_filepath))])

            # [可靠性提升] 延长清理 TTL 至 60 秒，确保发送链路彻底走完
            async def cleanup_temp_file(filepath: Path):
                await asyncio.sleep(60)
                if filepath.exists():
                    try:
                        filepath.unlink()
                    except Exception as e:
                        logger.error(f"清理临时图片失败: {e}")
                        
            asyncio.create_task(cleanup_temp_file(temp_filepath))

        except asyncio.TimeoutError:
            yield event.plain_result("❌ 图片下载超时，请重试。")
        except Exception as e:
            logger.error(f"ailogo error: {e}")
            yield event.plain_result(f"❌ 生成失败: 图像格式可能不被支持或受损。")