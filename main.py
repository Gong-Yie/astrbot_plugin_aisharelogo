import os
import io
import re
import aiohttp
import asyncio
import uuid
from PIL import Image, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
# 引入 At 组件用于解析 @别人
from astrbot.api.message_components import Image as AstrImage, Plain, At

# 统一工作尺寸
WORK_WIDTH = 1000
WORK_HEIGHT = 1000

@register("ailogo", "YourName", "自动生成Logo覆盖图片的插件", "1.0.0")
class AILogoPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 初始化目录
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.font_dir = os.path.join(self.plugin_dir, "font")
        self.logo_dir = os.path.join(self.plugin_dir, "logo")
        
        os.makedirs(self.font_dir, exist_ok=True)
        os.makedirs(self.logo_dir, exist_ok=True)

    # ================= 图像处理核心 =================

    def get_dynamic_font(self, text, font_path, target_width_ratio=0.75):
        conf_size = self.config.get("font_size", 0)
        if conf_size > 0:
            try:
                return ImageFont.truetype(font_path, conf_size)
            except IOError:
                return ImageFont.load_default()

        target_width = WORK_WIDTH * target_width_ratio
        font_size = 50
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            logger.error(f"无法加载字体 '{font_path}'。")
            return ImageFont.load_default()

        while True:
            dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            bbox = dummy_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            if text_w >= target_width:
                break
            font_size += 5
            font = ImageFont.truetype(font_path, font_size)
        return font

    def draw_thick_shadow_text(self, draw, x, y, text, font, text_color, shadow_color, shadow_depth=8):
        for i in range(shadow_depth, 0, -1):
            draw.text((x + i, y + i), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=text_color)

    def process_image(self, base_image_bytes, bg_path, font_path, text_content, style_type, out_file_path):
        """核心处理逻辑，直接保存为临时文件"""
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

        # 保存为指定路径的临时文件
        canvas.save(out_file_path, format='PNG')
        return out_file_path

    # ================= 消息链深层提取 =================
    
    def extract_image_url(self, message_chain) -> str:
        """递归查找消息链及嵌套组件中的图片 URL"""
        if not message_chain:
            return None
        for comp in message_chain:
            if isinstance(comp, AstrImage):
                return getattr(comp, "url", getattr(comp, "file", None))
            # 探索引用、合并转发等深层嵌套
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
        fonts = [f for f in os.listdir(self.font_dir) if os.path.isfile(os.path.join(self.font_dir, f))]
        if not fonts:
            yield event.plain_result("font 文件夹为空，请先放入字体文件。")
            return
        yield event.plain_result("可用字体：\n" + "\n".join(fonts))

    @filter.command("lslogo")
    async def lslogo(self, event: AstrMessageEvent):
        logos = [f for f in os.listdir(self.logo_dir) if os.path.isfile(os.path.join(self.logo_dir, f))]
        if not logos:
            yield event.plain_result("logo 文件夹为空，请先放入模板文件。")
            return
        yield event.plain_result("可用样式模板：\n" + "\n".join(logos))

    @filter.command("changefont")
    async def changefont(self, event: AstrMessageEvent, font_name: str):
        if not os.path.exists(os.path.join(self.font_dir, font_name)):
            yield event.plain_result(f"❌ 字体 {font_name} 不存在于 font 目录中！")
            return
        self.config["default_font"] = font_name
        self.config.save_config()
        yield event.plain_result(f"✅ 字体已成功切换为 {font_name}")

    @filter.command("changelogo")
    async def changelogo(self, event: AstrMessageEvent, logo_name: str):
        if not os.path.exists(os.path.join(self.logo_dir, logo_name)):
            yield event.plain_result(f"❌ 模板 {logo_name} 不存在于 logo 目录中！")
            return
        self.config["default_logo"] = logo_name
        self.config.save_config()
        yield event.plain_result(f"✅ 模板样式已成功切换为 {logo_name}")

    @filter.command("ailogo")
    async def ailogo(self, event: AstrMessageEvent):
        # 1. 规范提取文字：AstrBot 的 message_str 只会拼接纯文本，自动过滤图文和 @
        full_text = event.message_str.strip()
        parts = full_text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            text_content = parts[1].strip()
        else:
            text_content = "分10亿"

        # 2. 检查前置配置与素材状态
        font_file = self.config.get("default_font", "")
        logo_file = self.config.get("default_logo", "")
        font_path = os.path.join(self.font_dir, font_file)
        bg_path = os.path.join(self.logo_dir, logo_file)

        if not font_file or not os.path.exists(font_path):
            yield event.plain_result("❌ 请先在配置面板设置 default_font 或使用 /changefont 设置有效字体。")
            return
        if not logo_file or not os.path.exists(bg_path):
            yield event.plain_result("❌ 请先在配置面板设置 default_logo 或使用 /changelogo 设置有效模板。")
            return

        # 3. 优先级策略解析目标图像
        message_chain = event.get_messages()
        
        # 优先级 1：提取真实图片（涵盖场景 1、2、3）
        image_url = self.extract_image_url(message_chain)
        
        # 平台底层的正则兜底（针对未被框架展平的图片）
        if not image_url:
            raw_msg = getattr(event.message_obj, "raw_message", {})
            raw_str = str(raw_msg)
            match = re.search(r'(https?://(?:[^/]+\.)?qpic\.cn/[^\]\'",\s]+)', raw_str)
            if not match:
                match = re.search(r'url=(https?://[^\]\'",\s]+)', raw_str)
            if match:
                image_url = match.group(1)

        # 优先级 2 & 3：没有图片时的头像兜底逻辑
        if not image_url:
            target_qq = None
            # 寻找 @ 目标（涵盖场景 5）
            for comp in message_chain:
                if isinstance(comp, At):
                    target_qq = getattr(comp, "qq", getattr(comp, "id", None))
                    break
            
            if target_qq:
                # 场景 5：有 @ 对象，明确使用被 @ 人的头像
                image_url = f"http://q1.qlogo.cn/g?b=qq&nk={target_qq}&s=640"
            elif self.config.get("use_avatar_if_no_image", True):
                # 场景 4：没图也没 @，但配置开启了使用自身头像兜底
                sender_id = event.get_sender_id()
                image_url = f"http://q1.qlogo.cn/g?b=qq&nk={sender_id}&s=640"
            else:
                yield event.plain_result("❌ 缺少图片。请在发送指令时附带图片、引用图片，或 @ 一名群友。")
                return

        # 4. 获取图片数据并生成
        yield event.plain_result("🚀 正在生成中，请稍候...")
        img_data = None
        try:
            if image_url.startswith("http"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status != 200:
                            yield event.plain_result("❌ 无法下载图片，请重试。")
                            return
                        img_data = await resp.read()
            elif os.path.exists(image_url):  
                with open(image_url, "rb") as f:
                    img_data = f.read()
            else:
                yield event.plain_result("❌ 无法识别的图片来源。")
                return
            
            style_type = self.config.get("style_type", 1)
            
            # 临时文件保证阅后即焚，不占用服务器硬盘
            temp_filename = f"temp_logo_{uuid.uuid4().hex}.png"
            temp_filepath = os.path.join(self.plugin_dir, temp_filename)
            
            self.process_image(img_data, bg_path, font_path, text_content, style_type, temp_filepath)

            # 5. 返回合成好的图片
            yield event.chain_result([AstrImage.fromFileSystem(temp_filepath)])

            # 6. 异步清理任务
            async def cleanup_temp_file(filepath):
                await asyncio.sleep(3)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        logger.error(f"清理临时图片失败: {e}")
                        
            asyncio.create_task(cleanup_temp_file(temp_filepath))

        except Exception as e:
            logger.error(f"ailogo error: {e}")
            yield event.plain_result(f"❌ 生成失败: {str(e)}")