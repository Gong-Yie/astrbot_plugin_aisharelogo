import io
import re
import aiohttp
import asyncio
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Image as AstrImage, Plain, At

# 统一工作尺寸
WORK_WIDTH = 1000
WORK_HEIGHT = 1000

@register("aisharelogo", "工一阵", "制作分钱logo", "1.0")
class AILogoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 1. 插件源码自带目录 (存放 GitHub 上克隆下来的默认素材)
        self.plugin_dir = Path(__file__).parent
        self.plugin_font_dir = self.plugin_dir / "font"
        self.plugin_logo_dir = self.plugin_dir / "logo"
        
        # 2. 用户数据标准目录 (推荐用户自己添加素材的地方，防止更新被覆盖)
        self.data_dir = StarTools.get_data_dir("ailogo")
        self.data_font_dir = self.data_dir / "font"
        self.data_logo_dir = self.data_dir / "logo"
        
        # 确保目录存在
        self.plugin_font_dir.mkdir(parents=True, exist_ok=True)
        self.plugin_logo_dir.mkdir(parents=True, exist_ok=True)
        self.data_font_dir.mkdir(parents=True, exist_ok=True)
        self.data_logo_dir.mkdir(parents=True, exist_ok=True)

    # ================= 资源寻址工具 =================

    def get_asset_path(self, filename: str, asset_type: str) -> Path:
        """双目录寻址：优先从 data_dir 找，找不到再去 plugin_dir 找"""
        if not filename:
            return None
            
        data_path = self.data_font_dir if asset_type == "font" else self.data_logo_dir
        plugin_path = self.plugin_font_dir if asset_type == "font" else self.plugin_logo_dir
        
        # 优先查找用户数据目录
        target1 = data_path / filename
        if target1.exists() and target1.is_file():
            return target1
            
        # 兜底查找插件自带目录
        target2 = plugin_path / filename
        if target2.exists() and target2.is_file():
            return target2
            
        return None

    def get_all_assets(self, asset_type: str) -> list[str]:
        """合并双目录中的所有素材文件，并去重"""
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

        while font_size < max_font_size:
            dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
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
    
    def extract_image_url(self, message_chain) -> str:
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
        """切换默认字体"""
        safe_font_name = Path(font_name).name
        if not self.get_asset_path(safe_font_name, "font"):
            yield event.plain_result(f"字体 {safe_font_name} 不存在于任何 font 目录中！")
            return
        self.config["default_font"] = safe_font_name
        self.config.save_config()
        yield event.plain_result(f"字体已成功切换为 {safe_font_name}")

    @filter.command("changelogo")
    async def changelogo(self, event: AstrMessageEvent, logo_name: str):
        """切换默认模板"""
        safe_logo_name = Path(logo_name).name
        if not self.get_asset_path(safe_logo_name, "logo"):
            yield event.plain_result(f"模板 {safe_logo_name} 不存在于任何 logo 目录中！")
            return
        self.config["default_logo"] = safe_logo_name
        self.config.save_config()
        yield event.plain_result(f"模板样式已成功切换为 {safe_logo_name}")

    @filter.command("ailogo")
    async def ailogo(self, event: AstrMessageEvent):
        """主指令：生成 Logo 图片，支持附带文本、图片、引用图片、@ 群友等多种方式输入参数。"""
        full_text = event.message_str.strip()
        parts = full_text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            text_content = parts[1].strip()
        else:
            text_content = "分10亿"

        font_file = self.config.get("default_font", "")
        logo_file = self.config.get("default_logo", "")
        
        # 动态寻址
        font_path = self.get_asset_path(font_file, "font")
        bg_path = self.get_asset_path(logo_file, "logo")

        if not font_file or not font_path:
            yield event.plain_result("请先在配置面板设置 default_font 或使用 /changefont 设置有效字体。")
            return
        if not logo_file or not bg_path:
            yield event.plain_result("请先在配置面板设置 default_logo 或使用 /changelogo 设置有效模板。")
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
                image_url = f"http://q1.qlogo.cn/g?b=qq&nk={target_qq}&s=640"
            elif self.config.get("use_avatar_if_no_image", True):
                sender_id = event.get_sender_id()
                image_url = f"http://q1.qlogo.cn/g?b=qq&nk={sender_id}&s=640"
            else:
                yield event.plain_result("缺少图片。请在发送指令时附带图片、引用图片，或 @ 一名群友。")
                return

        yield event.plain_result("正在生成中，请稍候...")
        
        try:
            img_data = None
            if image_url.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status != 200:
                            yield event.plain_result(f"无法下载图片，网络状态码: {resp.status}")
                            return
                        img_data = await resp.read()
            elif Path(image_url).exists():  
                img_data = Path(image_url).read_bytes()
            else:
                yield event.plain_result("无法识别的图片来源。")
                return
            
            style_type = self.config.get("style_type", 1)
            temp_filename = f"temp_logo_{uuid.uuid4().hex}.png"
            temp_filepath = self.data_dir / temp_filename
            
            await asyncio.tothread(
                self.process_image,
                img_data, str(bg_path), str(font_path), text_content, style_type, str(temp_filepath)
            )

            yield event.chain_result([AstrImage.fromFileSystem(str(temp_filepath))])

            async def cleanup_temp_file(filepath: Path):
                await asyncio.sleep(3)
                if filepath.exists():
                    try:
                        filepath.unlink()
                    except Exception as e:
                        logger.error(f"清理临时图片失败: {e}")
                        
            asyncio.create_task(cleanup_temp_file(temp_filepath))

        except Exception as e:
            logger.error(f"ailogo error: {e}")
            yield event.plain_result(f"生成失败: {str(e)}")