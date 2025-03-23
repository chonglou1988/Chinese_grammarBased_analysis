"""
小说文本清理工具
功能：自动清理小说文本中的广告、特殊符号，智能提取章节并保存为单独文件
作者：Max Li
创建时间：2025年3月23日
"""

import re
import os
import logging
from chardet import detect
from natsort import natsorted

class NovelCleaner:
    MAX_TITLE_LENGTH = 25  # 限制章回标题最大长度

    def __init__(self, file_path):
        self.file_path = file_path
        self.raw_text = ""
        self.chapters = []
        self._setup_logger()

    def _setup_logger(self):
        """配置日志系统"""
        self.logger = logging.getLogger('NovelCleaner')
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            file_handler = logging.FileHandler('novel_clean.log', encoding='utf-8')
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(levelname)s: %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def _load_file(self):
        """加载并解码文件"""
        try:
            with open(self.file_path, 'rb') as f:
                raw_data = f.read()
                result = detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                self.logger.info(f"检测到文件编码: {encoding} (置信度: {result.get('confidence', 0):.2f})")
                self.raw_text = raw_data.decode(encoding, errors='replace')
                self.logger.info(f"成功加载文件，长度: {len(self.raw_text)} 字符")
        except Exception as e:
            self.logger.exception("文件加载失败")
            raise

    def _clean_content(self):
        """内容清理增强版"""
        ad_patterns = [
            (r'http[s]?://\S+', 'URL链接'),
            (r'关注[^，。]{5,20}(公众号|微信号)', '公众号广告'),
            (r'QQ群\d{5,11}', 'QQ群广告'),
            (r'（请记得收藏本站[^）]+）', '站内广告'),
            (r'\d{8,}', '长数字广告'),
            (r'={4,}.*?={4,}', '分隔符广告'),
            (r'[^\n]{20,}精校[^\n]{20,}', '校对声明'),
            (r'更多免费', '推广广告'),
            (r'[\u25A0-\u25FF\u2605-\u2606\uFF08-\uFF09]+', '特殊符号')
        ]
        compiled_ads = [(re.compile(pattern), desc) for pattern, desc in ad_patterns]
        for pattern, desc in compiled_ads:
            self.raw_text, count = pattern.subn('', self.raw_text)
            if count > 0:
                self.logger.info(f"清理广告 [{desc}] → 删除{count}处")

        # 统一换行符，合并多余空行和连续空格
        self.raw_text = re.sub(r'\r\n|\r', '\n', self.raw_text)
        self.raw_text = re.sub(r'\n{3,}', '\n\n', self.raw_text)
        self.raw_text = re.sub(r'[ \t　]{2,}', ' ', self.raw_text)

    def _parse_chapter(self, match, ptype, expected_chapter_num):
        """根据匹配结果解析章节号和标题"""
        if ptype in ['std_chapter', 'hui_chapter']:
            num_part = match.group(1)
            title = match.group(2)
            chapter_num = self._chinese_to_arabic(num_part[1:-1])  # 去掉“第”和“章/回”
        elif ptype == 'cn_num':
            num_part = match.group(1)
            title = match.group(2)
            chapter_num = self._chinese_to_arabic(num_part)
        elif ptype == 'ar_num':
            num_part = match.group(1)
            title = match.group(2)
            chapter_num = int(num_part)
        else:  # deco_chapter
            num_part = match.group(1)
            title = match.group(2)
            if num_part[0] in '章节卷集':
                num_part = num_part[1:]
            if num_part.isdigit():
                chapter_num = int(num_part)
            else:
                chapter_num = self._chinese_to_arabic(num_part)
        return chapter_num, title

    def _extract_chapters(self):
        """
        智能章节提取引擎：
        - 章节标题必须以换行开始，且后接换行符（独立成行）
        - 标题长度限制为 MAX_TITLE_LENGTH 个字符
        - 章节编号必须递增，否则视为正文内容
        """
        chapter_patterns = [
            # 标准章节格式：第X章 标题
            (rf'(?:^|\n)(第[零一二三四五六七八九十百千万]+章)[ 　]*(.{{1,{self.MAX_TITLE_LENGTH}}})\n', 'std_chapter'),
            # 回/卷格式：第X回 标题
            (rf'(?:^|\n)(第[零一二三四五六七八九十百千万]+回)[ 　]*(.{{1,{self.MAX_TITLE_LENGTH}}})\n', 'hui_chapter'),
            # 中文数字标题（有空格）：[数字] 空格 [标题]
            (rf'(?:^|\n)([零一二三四五六七八九十百千万]+)[ 　]+(.{{1,{self.MAX_TITLE_LENGTH}}})\n', 'cn_num'),
            # 阿拉伯数字标题：数字. 标题
            (rf'(?:^|\n)(\d{{1,4}})[.．、 ]+(.{{1,{self.MAX_TITLE_LENGTH}}})\n', 'ar_num'),
            # 装饰符号标题：可能有特殊符号开头
            (rf'(?:^|\n)[●★◆□■▣]?([章节卷集]?[\d零一二三四五六七八九十百千万]+)[ 　\-－~～]*(.{{1,{self.MAX_TITLE_LENGTH}}})\n', 'deco_chapter')
        ]
        compiled_patterns = [(re.compile(pat, re.MULTILINE), ptype) for pat, ptype in chapter_patterns]

        matches = []
        for pattern, ptype in compiled_patterns:
            for match in pattern.finditer(self.raw_text):
                matches.append((match.start(), match.end(), ptype, match))
        matches.sort(key=lambda x: x[0])

        chapters = []
        last_pos = 0
        expected_chapter_num = 1  # 假设章节从1开始
        for start, end, ptype, match in matches:
            # 忽略重叠区域
            if start < last_pos:
                continue

            # 解析新章节的编号和标题
            new_chapter_num, title = self._parse_chapter(match, ptype, expected_chapter_num)

            # 如果新章节编号不等于预期的编号，则忽略该匹配
            if new_chapter_num != expected_chapter_num:
                self.logger.debug(f"忽略非连续章节：{match.group(0).strip()} (预期 {expected_chapter_num}, 实际 {new_chapter_num})")
                continue

            # 章节之间的内容作为正文处理
            if start > last_pos:
                inter_content = self.raw_text[last_pos:start].strip()
                if chapters:
                    prev_title, prev_content = chapters.pop()
                    chapters.append((prev_title, prev_content + '\n' + inter_content))
                else:
                    chapters.append(('前言', inter_content))

            # 更新章节号并记录新章节
            clean_title = f"第{new_chapter_num}章 {title.strip()}"
            chapters.append((clean_title, ""))
            last_pos = end
            expected_chapter_num += 1  # 更新预期编号

        # 处理末尾未匹配的正文内容
        if last_pos < len(self.raw_text):
            final_content = self.raw_text[last_pos:].strip()
            if chapters:
                last_title, last_content = chapters.pop()
                chapters.append((last_title, last_content + '\n' + final_content))
            else:
                chapters.append(('全文', final_content))

        self.chapters = [(t, c.strip()) for t, c in chapters if c.strip()]
        self.logger.info(f"检测到有效章节数量: {len(self.chapters)}")

    def _chinese_to_arabic(self, cn_num: str) -> int:
        """增强版中文数字转换"""
        cn_num_map = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '百': 100, '千': 1000, '万': 10000, '亿': 100000000
        }
        total = 0
        section = 0
        temp = 0
        for char in cn_num:
            value = cn_num_map.get(char, 0)
            if value >= 10000:
                section = (section + temp) * value
                total += section
                section = 0
                temp = 0
            elif value >= 100:
                temp = temp * value if temp != 0 else value
                section += temp
                temp = 0
            elif value >= 10:
                temp = temp * value if temp != 0 else value
            else:
                temp += value
        total += section + temp
        return total if total > 0 else 1  # 确保编号不为0

    def _sanitize_filename(self, name: str) -> str:
        """文件名规范化处理"""
        name = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', name)
        return re.sub(r'[\\/*?:"<>|]', '_', name).strip(' ._')

    def process(self, output_dir="cleaned"):
        """处理主流程"""
        try:
            self._load_file()
            self._clean_content()
            self._extract_chapters()

            if not self.chapters:
                self.logger.warning("未检测到章节，生成全文文件")
                self.chapters = [('全文', self.raw_text)]

            os.makedirs(output_dir, exist_ok=True)
            self.logger.info(f"创建输出目录: {os.path.abspath(output_dir)}")

            for idx, (title, content) in enumerate(self.chapters, 1):
                safe_title = self._sanitize_filename(title)[:40]
                filename = f"{idx:04d}_{safe_title}.txt" if safe_title else f"{idx:04d}.txt"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"【{title}】\n{content}")
                    self.logger.debug(f"生成文件: {filename} ({len(content)}字符)")
            self.logger.info(f"成功生成 {len(self.chapters)} 个章节文件")
            print(f"处理完成！输出目录: {os.path.abspath(output_dir)}")
        except Exception as e:
            self.logger.exception("处理失败")
            raise

if __name__ == "__main__":
    cleaner = NovelCleaner("天龙八部·txt.txt")
    cleaner.process()
文件内容已省略，使用实际文件内容
