import re
import jieba
import jieba.posseg as pseg
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import json  # 用于保存设置


# 定义文章处理类
class ArticleProcessor:
    def __init__(self, synonym_path, synonym_freq=1000):
        """
        初始化文章处理器
        :param synonym_path: 同义词文件路径（格式：原词 空格 替换词）
        :param synonym_freq: 添加到分词词典的词频
        """
        self.synonyms = defaultdict(list)  # 用于存储同义词库数据
        self.synonym_freq = synonym_freq
        self.load_synonyms(synonym_path)  # 加载同义词库
        self._init_jieba()  # 初始化 jieba 分词配置

    def _init_jieba(self):
        """
        将同义词库中的词加入 jieba 分词词典，确保分词时不会错误拆分
        """
        for word in self.synonyms.keys():
            jieba.add_word(word, freq=self.synonym_freq)
        jieba.initialize()

    def load_synonyms(self, path):
        """
        从文件中加载同义词库，文件格式要求：每行两个词，以空格隔开，第一个为原词，第二个为替换词
        :param path: 同义词库文件路径
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = re.split(r'\s+', line, 1)
                    if len(parts) == 2:
                        orig, replace = parts
                        self.synonyms[orig].append(replace)
        except Exception as e:
            messagebox.showerror("错误", f"加载同义词库失败：{e}")

    def _condense_sentence(self, sentence):
        """
        对句子进行浓缩处理，剔除冗余成分并只保留核心词汇：
          1. 利用正则表达式删除时间状语等冗余成分
          2. 分词后保留名词（n）、动词（v）、形容词（a）以及部分转折连词
        :param sentence: 原始句子
        :return: 浓缩后的句子
        """
        sentence = re.sub(r'当.*?时，?|尽管.*?，?|虽然.*?但是', '', sentence)
        words = pseg.cut(sentence)
        kept_words = []
        for word, pos in words:
            if pos[0] in ['n', 'v', 'a'] and len(word) > 1:
                kept_words.append(word)
            elif word in ["但是", "然而"]:
                kept_words.append(word)
        if not kept_words:
            return ""
        condensed = []
        for i in range(len(kept_words)):
            if i > 0 and kept_words[i - 1] in ["但是", "然而"]:
                condensed.append(kept_words[i])
            elif kept_words[i] not in condensed:
                condensed.append(kept_words[i])
        return "".join(condensed)

    def _replace_words(self, text):
        """
        对文本进行同义词替换：
        1. 采用 jieba 分词后，若词出现在同义词库中，则替换为对应的替换词。
        2. 为保证长词优先替换，先按照词长降序匹配原词。
        :param text: 待处理文本
        :return: 替换后的文本
        """
        words = jieba.lcut(text)
        replaced = []
        current_index = 0
        for word in words:
            if word in self.synonyms:
                replaced_flag = False
                for orig in sorted(self.synonyms.keys(), key=lambda x: len(x), reverse=True):
                    if text.startswith(orig, current_index):
                        replaced.append(self.synonyms[orig][0])
                        current_index += len(orig)
                        replaced_flag = True
                        break
                if not replaced_flag:
                    replaced.append(self.synonyms[word][0])
                    current_index += len(word)
            else:
                replaced.append(word)
                current_index += len(word)
        return ''.join(replaced)

    def process(self, text, contrast=False):
        """
        处理全文：
          1. 保留原有段落结构
          2. 对每个句子进行浓缩和同义词替换
          3. 可选生成每个句子修改前后的对照信息
        :param text: 原始文章文本
        :param contrast: 是否生成句子修改前后对照结果
        :return: 返回处理后的文本及（可选的）对照列表；对照列表元素格式为 (原始句子, 修改后句子)
        """
        paragraphs = text.split('\n')
        processed_paragraphs = []
        contrast_pairs = []

        for para in paragraphs:
            if not para.strip():
                processed_paragraphs.append("")
                continue
            sentences = re.split(r'([。！？])', para)
            new_sentences = []
            buffer = []
            for seg in sentences:
                if seg in ["。", "！", "？"]:
                    if buffer:
                        orig_sentence = ''.join(buffer).strip()
                        condensed = self._condense_sentence(orig_sentence)
                        replaced = self._replace_words(condensed)
                        new_sentences.append(replaced + seg)
                        if orig_sentence and replaced:
                            contrast_pairs.append((orig_sentence + seg, replaced + seg))
                        buffer = []
                else:
                    buffer.append(seg)
            processed_paragraphs.append(''.join(new_sentences))
        processed_text = '\n'.join(processed_paragraphs)
        if contrast:
            return processed_text, contrast_pairs
        else:
            return processed_text


# 定义 GUI 应用类
class ArticleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("文章处理去AI")
        self.root.geometry("900x700")

        # 载入上次设置
        self.settings_path = "article_app_settings.json"
        self.load_settings()

        # 初始化变量
        self.file_path = tk.StringVar()
        self.synonym_path = tk.StringVar(value=self.settings.get("synonym_path", "_internal/lexicon.txt"))
        self.frequency = tk.IntVar(value=self.settings.get("frequency", 1000))
        self.contrast = tk.BooleanVar(value=self.settings.get("contrast", False))
        self.font_size = tk.IntVar(value=self.settings.get("font_size", 12))

        # 构建界面
        self.build_interface()

    def load_settings(self):
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        except:
            self.settings = {}

    def save_settings(self):
        self.settings = {
            "synonym_path": self.synonym_path.get(),
            "frequency": self.frequency.get(),
            "contrast": self.contrast.get(),
            "font_size": self.font_size.get(),
        }
        with open(self.settings_path, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def build_interface(self):
        file_frame = tk.Frame(self.root)
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(file_frame, text="文章文件：").pack(side=tk.LEFT)
        tk.Entry(file_frame, textvariable=self.file_path, width=50).pack(side=tk.LEFT, padx=5)
        tk.Button(file_frame, text="浏览", command=self.browse_file).pack(side=tk.LEFT)

        option_frame = tk.Frame(self.root)
        option_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(option_frame, text="词频：").pack(side=tk.LEFT)
        tk.Entry(option_frame, textvariable=self.frequency, width=10).pack(side=tk.LEFT, padx=5)
        tk.Checkbutton(option_frame, text="输出修改前后对照", variable=self.contrast).pack(side=tk.LEFT, padx=10)
        tk.Label(option_frame, text="字体大小：").pack(side=tk.LEFT)
        tk.Spinbox(option_frame, from_=8, to=24, textvariable=self.font_size, width=5, command=self.update_font).pack(side=tk.LEFT)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(padx=10, pady=5)
        tk.Button(btn_frame, text="开始处理", command=self.start_processing).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="清空", command=self.clear_text).pack(side=tk.LEFT, padx=5)

        input_frame = tk.Frame(self.root)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(input_frame, text="输入原文或载入文件：").pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=10, font=("微软雅黑", self.font_size.get()))
        self.input_text.pack(fill=tk.BOTH, expand=True)

        output_frame = tk.Frame(self.root)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tk.Label(output_frame, text="处理结果：").pack(anchor=tk.W)
        self.result_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=10, font=("微软雅黑", self.font_size.get()))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        self.contrast_text = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=10, font=("微软雅黑", self.font_size.get()))

    def update_font(self):
        new_font = ("微软雅黑", self.font_size.get())
        self.input_text.configure(font=new_font)
        self.result_text.configure(font=new_font)
        self.contrast_text.configure(font=new_font)
        self.save_settings()

    def browse_file(self):
        path = filedialog.askopenfilename(title="选择文章文件", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if path:
            self.file_path.set(path)
            with open(path, 'r', encoding='utf-8') as f:
                self.input_text.delete(1.0, tk.END)
                self.input_text.insert(tk.END, f.read())

    def start_processing(self):
        article_text = self.input_text.get(1.0, tk.END).strip()
        if not article_text:
            messagebox.showwarning("提示", "请输入文章内容或载入文件。")
            return
        processor = ArticleProcessor(self.synonym_path.get(), synonym_freq=self.frequency.get())
        try:
            if self.contrast.get():
                processed_text, contrast_pairs = processor.process(article_text, contrast=True)
            else:
                processed_text = processor.process(article_text)
        except Exception as e:
            messagebox.showerror("错误", f"处理文章时出错：{e}")
            return

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, processed_text)

        if self.contrast.get():
            self.contrast_text.delete(1.0, tk.END)
            self.contrast_text.insert(tk.END, "=== 原句与处理后句对照 ===\n")
            for idx, (orig, new) in enumerate(contrast_pairs, start=1):
                self.contrast_text.insert(tk.END, f"句子 {idx}:\n原句：{orig}\n处理后：{new}\n{'-' * 40}\n")
            if not self.contrast_text.winfo_ismapped():
                self.contrast_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        else:
            self.contrast_text.pack_forget()
        self.save_settings()

    def clear_text(self):
        self.input_text.delete(1.0, tk.END)
        self.result_text.delete(1.0, tk.END)
        self.contrast_text.delete(1.0, tk.END)


# 主程序入口
if __name__ == "__main__":
    root = tk.Tk()
    app = ArticleApp(root)
    root.mainloop()