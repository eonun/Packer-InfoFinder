# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
from lib.Controller import Project
from lib.TestProxy import testProxy
from lib.common.banner import RandomBanner
from lib.common.cmdline import CommandLines
from lib.common.readConfig import ReadConfig



class Program():
    def __init__(self,options):
        self.options = options

    def check(self):
        url = self.options.url
        t = Project(url,self.options)
        t.parseStart()


def read_urls(file_path):
    """读取 URL 文件"""
    try:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件 {file_path} 不存在")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except (FileNotFoundError, IOError, PermissionError) as e:
        print(f"文件操作失败: {e}")
        exit(1)
def PackerInfoFinder():
    options = CommandLines().cmd()
    if options.url == None:
        urls = read_urls(options.list)
        total_urls = len(urls)

        if total_urls == 0:
            print("urls.txt 文件为空或无有效 URL")
            exit(1)

        print(f"开始扫描 {total_urls} 个 URL...")

        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{total_urls}] 开始扫描 URL: {url}")
            print("=====================")
            testProxy(options,1)
            options.url = url
            InfoFinder = Program(options)
            InfoFinder.check()
        print(f"\n所有 {total_urls} 个 URL 扫描完毕")
    else:
        testProxy(options, 1)
        PackerFuzzer = Program(options)
        PackerFuzzer.check()

if __name__ == "__main__":
    PackerInfoFinder()

