import os
import json
import re
from natsort import natsorted

class NovelToJsonConverter:
    def __init__(self, input_dir="cleaned"):
        self.input_dir = input_dir
        self.novel_data = {
            "title": "",
            "author": "",
            "chapters": []
        }

    def _extract_metadata(self, content):
        """从内容中提取书名和作者信息"""
        # 查找书名和作者信息
        title_pattern = r"【.*?】\n.*\n.*\n(.*?)\n作者[:：]"
        author_pattern = r"作者[:：]\s*(\S+)"
        
        title_match = re.search(title_pattern, content)
        author_match = re.search(author_pattern, content)
        
        if title_match:
            self.novel_data["title"] = title_match.group(1)
        if author_match:
            self.novel_data["author"] = author_match.group(1)
        
        # 设置输出文件名
        if self.novel_data["title"]:
            self.output_file = f"{self.novel_data['title']}.json"
        else:
            self.output_file = "novel.json"

    def _extract_chapter_info(self, filename):
        """从文件名中提取章节编号和标题"""
        match = re.match(r"(\d{4})_(.*)\.txt", filename)
        if match:
            chapter_num = int(match.group(1))
            chapter_title = match.group(2)
            return chapter_num, chapter_title
        return None, None

    def _read_chapter_content(self, filepath):
        """读取章节内容"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        # 去除章节标题行（如果有）
        if content.startswith("【"):
            content = content.split("\n", 1)[1]
        return content.strip()

    def convert(self):
        """主转换方法"""
        # 获取所有txt文件并按自然顺序排序
        files = [f for f in os.listdir(self.input_dir) if f.endswith(".txt")]
        files = natsorted(files)

        # 从第一个文件中提取元数据
        if files:
            first_file = os.path.join(self.input_dir, files[0])
            with open(first_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._extract_metadata(content)

        for filename in files:
            chapter_num, chapter_title = self._extract_chapter_info(filename)
            if chapter_num is None:
                continue

            filepath = os.path.join(self.input_dir, filename)
            content = self._read_chapter_content(filepath)

            chapter_data = {
                "chapter_number": chapter_num,
                "chapter_title": chapter_title,
                "content": content
            }
            self.novel_data["chapters"].append(chapter_data)

        # 保存为JSON文件
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.novel_data, f, ensure_ascii=False, indent=2)

        print(f"转换完成！已保存为 {self.output_file}")

if __name__ == "__main__":
    converter = NovelToJsonConverter()
    converter.convert()
