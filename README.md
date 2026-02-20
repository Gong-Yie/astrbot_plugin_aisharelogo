<div align="center">

![astrbot_plugin_aisharelogo](https://count.getloli.com/@astrbot_plugin_aisharelogo?name=astrbot_plugin_aisharelogo&theme=original-new&padding=7&offset=0&align=center&scale=1&pixelated=1&darkmode=auto)

# **astrbot_plugin_aisharelogo**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.0%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Gong_Yie-blue)](https://github.com/Gong-Yie)

</div>

一个生成"分多少亿"图片的插件，灵感来源自最近国内各大ai都在搞的分多少多少亿的活动

---

## ✨ 核心特性
 
* **双重文字特效**：支持“立体深红厚重阴影（红包风格）”与“纯色扁平风格”两种视觉特效。  
* **动态字体排版**：根据图片尺寸和文字长度智能自动计算并自适应缩放巨型字体大小。  
* **阅后即焚机制**：合成过程采用临时文件策略，图片发送后 3 秒内自动物理删除，保证服务器硬盘 **0 垃圾堆积**，高并发下依然稳定不串图。

---

## 📥 安装方法

### **手动安装**

1. 进入 AstrBot 的插件目录：  

```Bash
cd data/plugins
```

2. 克隆本仓库（或将插件文件夹上传至此目录）：  

```Bash
git clone https://github.com/Gong-Yie/astrbot_plugin_aisharelogo
```

3. 安装依赖库（通常 AstrBot 环境已包含 PIL 与 aiohttp，若无请安装）：  

```Bash  
pip install Pillow aiohttp
```

4. **重启 AstrBot**。

---

## 📂 目录结构与资源放置

插件第一次启动后，会自动在插件目录下生成 font 和 logo 两个文件夹。**请务必手动将您的自定义资源放入对应文件夹中**：

```Plaintext

AstrBot根目录/  
├── data/  
│   └── plugins/  
│       └── astrbot_plugin_aisharelogo/   <-- 插件数据主目录  
│           ├── font/                <-- 【在此放入字体文件】(.ttf, .otf, .ttc)  
│           ├── logo/                <-- 【在此放入底图模板】(.png, 建议上透明下红底)  
│           ├── main.py              <-- 插件核心代码  
│           └── _conf_schema.json    <-- WebUI 配置文件
```

---

## ⚙️ 配置说明

请在 AstrBot 管理面板 -> **插件** -> **astrbot_plugin_aisharelogo** -> **配置** 中进行设置。

| 配置项 | 类型 | 默认值 | 说明 |
| :---- | :---- | :---- | :---- |
| **自定义字体大小** | Int | 0 | 若为 0 则根据图片宽度自动计算。强烈建议保持为 0。 |
| **默认字体文件** | String | 优设标题黑.ttf | **重点**：填写 font/ 下的文件名（含后缀），例如 Alimama.ttf。 |
| **默认模板文件** | String | style1_bg.png | **重点**：填写 logo/ 下的文件名（含后缀），例如 bg_red.png。 |
| **文字特效样式** | Int | 1 | 1 为深红立体阴影，2 为纯色扁平文字。 |
| **无图时使用头像兜底** | Bool | True | 当用户指令未附带图片且未 @ 任何人时，是否自动抓取该用户的 QQ 头像作为底图。 |

---

## 🎮 指令使用

### **1. 核心生成指令**

* **指令**：/ailogo [文字内容] [图片]
* **作用**：生成 Logo 覆盖图片。如果不输入文字内容，默认会使用“分10亿”。  
* **用法场景**：  
  * **直接发图**：/ailogo 分10亿 （并在同一条消息中附带一张图片）  
  * **引用发图**：回复群友的图片，配文 /ailogo 拿来吧你  
  * **@群友发图**：/ailogo 分10亿 @张三 （自动抓取张三头像）  
  * **自娱自乐**：/ailogo 分10亿 （不带图不带艾特，需要在配置中开启默认抓取头像）

### **2. 素材管理指令**

* **/lsfont**：查看 font/ 目录下所有可用的字体文件。  
* **/lslogo**：查看 logo/ 目录下所有可用的模板底图。  
* **/changefont <文件名>**：快捷切换 WebUI 配置中的默认字体。  
* **/changelogo <文件名>**：快捷切换 WebUI 配置中的默认底图。

---

## ⚠️ 注意事项与常见问题 (FAQ)

### **Q1: 为什么提示“无法加载字体”或“模板不存在”？**

* **解决**：  
  1. 请确保您已经把 .ttf 文件放入了 font 文件夹，把 .png 文件放入了 logo 文件夹。  
  2. 请检查 WebUI 配置面板中填写的文件名是否**完全一致**（包括大小写和后缀名）。

### **Q2: 图片比例看起来被拉伸了？**

为了保证生成效果的一致性，插件会将所有输入的图片强制调整缩放至 1000x1000 的统一画布。建议您在使用时尽量选择比例接近正方形（1:1）的图片。

---

## 📝 免责声明

* 使用目的：本插件仅供学习交流，使用者不得用于非法或侵权行为，否则自行承担全部责任。  
* 功能限制：本插件仅通过 onebot 协议获取公开信息，作者不对数据的准确性、完整性负责。  
* 禁止非法修改：严禁私自魔改本插件（如接入社工库等违规操作），违者自行承担法律责任。  
* 风险自担：使用者应自行评估使用风险，作者不对使用过程中产生的任何损失或风险承担责任。  
* 法律适用：本声明适用中华人民共和国法律，争议由作者所在地法院管辖。  
* 声明解释权：作者保留对本声明的最终解释权，并有权随时修改。
