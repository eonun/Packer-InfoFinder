#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os, re, sqlite3, subprocess
from urllib.parse import urlparse
from lib.common.utils import Utils
from lib.Database import DatabaseType
from lib.DownloadJs import DownloadJs
from lib.common.groupBy import GroupBy
from lib.common.CreatLog import creatLog
import deno_vm  # 替换 node_vm2 为 deno_vm


class RecoverSpilt():

    def __init__(self, projectTag, options):
        self.name_list = []
        self.remotePaths = []
        self.jsFileNames = []
        self.localFileNames = []
        self.remoteFileURLs = []
        self.js_compile_results = []
        self.projectTag = projectTag
        self.options = options
        self.log = creatLog().get_logger()

    def jsCodeCompile(self, jsCode, jsFilePath):
        try:
            self.log.info(Utils().tellTime() + "正在处理异步加载代码中...")  # 正在处理异步加载代码中
            variable = re.findall(r'\[.*?\]', jsCode)  # 提取 [e]
            if "[" and "]" in variable[0]:
                variable = variable[0].replace("[", "").replace("]", "") # 将 `[` 和 `]` 替换为空字符串
            # 封装成一个可调用的函数 js_compile，以便在 Node.js 环境中执行并返回计算后的 URL
            jsCodeFunc = "function js_compile(%s){js_url=" % (variable) + jsCode + "\nreturn js_url}" 
            """
            %s 是占位符，替换为变量名(如 e)
            最终生成类似 function js_compile(e){js_url= 的函数声明
            若 jsCode 是 "static/js/"+({}[e]||e)+"."+{"chunk-037f81c0":"a5ea1ede","chunk-07782ef6":"547d8958","chunk-12fca57e":"6415a309"}[e]+".js"
            则 jsCodeFunc 为 function js_compile(e){js_url="static/js/"+({}[e]||e)+"."+{"chunk-037f81c0":"a5ea1ede","chunk-07782ef6":"547d8958","chunk-12fca57e":"6415a309"}[e]+".js"}
            返回值为 js_url
            """
            pattern_jscode = re.compile(r"\(\{\}\[(.*?)\]\|\|.\)", re.DOTALL) # 匹配 `({})[` `]||` 中的值 例如 ({})[e]||e 为 e
            flag_code = pattern_jscode.findall(jsCodeFunc)
            if flag_code:
                jsCodeFunc = jsCodeFunc.replace("({}[%s]||%s)" % (flag_code[0], flag_code[0]), flag_code[0]) # 替换 `({})[e]||e` 为 e
            pattern1 = re.compile(r"\{(.*?)\:") # {"chunk-037f81c0":" --> "chunk-037f81c0"
            pattern2 = re.compile(r"\,(.*?)\:") # ,"chunk-07782ef6":" --> "chunk-07782ef6"
            nameList1 = pattern1.findall(jsCode)
            nameList2 = pattern2.findall(jsCode)
            nameList = nameList1 + nameList2 # 合并两个列表
            nameList = list(set(nameList)) # 去重
            projectDBPath = DatabaseType(self.projectTag).getPathfromDB() + self.projectTag + ".db"
            connect = sqlite3.connect(os.sep.join(projectDBPath.split('/')))
            cursor = connect.cursor() # 创建游标对象
            connect.isolation_level = None # 设置事务隔离级别
            localFile = jsFilePath.split(os.sep)[-1]
            sql = "insert into js_split_tree(jsCode,js_name) values('%s','%s')" % (jsCode, localFile)
            cursor.execute(sql) # 执行 SQL 语句
            connect.commit() # 提交事务
            cursor.execute("select id from js_split_tree where js_name='%s'" % (localFile))
            jsSplitId = cursor.fetchone()[0] # 获取 id
            cursor.execute("select path from js_file where local='%s'" % (localFile))
            jsUrlPath = cursor.fetchone()[0] # 获取路径
            connect.close()
            with deno_vm.VM() as vm:  # 替换 py_mini_racer.MiniRacer 为 deno_vm.VM
                vm.run(jsCodeFunc)
                for name in nameList:
                    if "\"" in name:
                        name = name.replace("\"", "")
                    if "undefined" not in vm.call("js_compile", name):
                        jsFileName = vm.call("js_compile", name)
                        self.jsFileNames.append(jsFileName)
            self.log.info(Utils().tellTime() + "异步JS文件提取成功，提取数量：" + str(len(self.jsFileNames))) # 异步JS文件提取成功，提取数量
            self.getRealFilePath(jsSplitId, self.jsFileNames, jsUrlPath)
            self.log.debug("jscodecomplie模块正常")
        except Exception as e:
            self.log.error("[Err] %s" % e)  # 这块有问题，逻辑要改进
            return 0

    def checkCodeSpilting(self, jsFilePath):
        jsOpen = open(jsFilePath, 'r', encoding='UTF-8',errors="ignore")  # 防编码报错
        jsFile = jsOpen.readlines()
        jsFile = str(jsFile)  # 二次转换防报错
        if "document.createElement(\"script\");" in jsFile:  # 判断JS异步加载
            self.log.info(
                Utils().tellTime() + "疑似存在JS异步加载：" + Utils().getFilename(jsFilePath))
            pattern = re.compile(r"\w\.p\+\"(.*?)\.js", re.DOTALL)  # 提取动态拼接的段落, `x.p+`  `.js` 之间的内容 ， 通过捕获组 (.*?) 明确指定需要提取的目标内容
            # c.p+"static/js/"+({}[e]||e)+"."+{"chunk-037f81c0":"a5ea1ede","chunk-07782ef6":"547d8958","chunk-12fca57e":"6415a309"}[e]+".js
            if pattern:
                jsCodeList = pattern.findall(jsFile) # static/js/"+({}[e]||e)+"."+{"chunk-037f81c0":"a5ea1ede","chunk-07782ef6":"547d8958","chunk-12fca57e":"6415a309"}[e]+"
                for jsCode in jsCodeList:
                    if len(jsCode) < 30000:
                        jsCode = "\"" + jsCode + ".js\""   # "static/js/"+({}[e]||e)+"."+{"chunk-037f81c0":"a5ea1ede","chunk-07782ef6":"547d8958","chunk-12fca57e":"6415a309"}[e]+".js"
                        self.jsCodeCompile(jsCode, jsFilePath)

    def getRealFilePath(self, jsSplitId, jsFileNames, jsUrlpath):
        """
        获取JavaScript文件的真实路径。
    
        根据JavaScript文件的URL路径和文件名，计算出其在服务器上的真实路径。
        这个方法处理两种情况：一种是HTML中通过<script>标签引入的JS文件，
        另一种是通过异步加载的JS文件。
    
        参数:
        - jsSplitId: JavaScript文件的分割ID，用于标识特定的JS文件。
        - jsFileNames: JavaScript文件名列表，表示需要处理的JS文件名。
        - jsUrlpath: JavaScript文件的URL路径，用于计算真实路径。
    
        返回值:
        无直接返回值，但会调用DownloadJs类的downloadJs方法下载JS文件。
        """
        # 我是没见过webpack异步加载的js和放异步的js不在同一个目录下的，这版先不管不同目录的情况吧
        # 初始化一个空列表，用于存储计算出的真实文件路径
        jsRealPaths = []

        # 使用urlparse解析jsUrlpath，获取URL的各个组成部分
        res = urlparse(jsUrlpath)

        # 解析self.options.url，确保即使JS文件和扫描目标不在同一域名下，数据库也能正常载入
        resForDB = urlparse(self.options.url)

        # 如果jsUrlpath中包含特殊标记"§§§"，表示这是HTML中通过<script>标签引入的JS文件
        if "§§§" in jsUrlpath:
            # 去掉"§§§"及其后面的内容，仅保留基础路径部分
            jsUrlpath = jsUrlpath.split('§§§')[0]
            
            # 将路径按"/"分割成列表
            tmpUrl = jsUrlpath.split("/")
            
            # 如果路径的最后一部分是文件名（包含"."），则删除这一部分
            if "." in tmpUrl[-1]:
                del tmpUrl[-1]
            
            # 拼接剩余部分，形成基础路径
            base_url = "/".join(tmpUrl)
            
            # 遍历jsFileNames列表，将每个文件名与基础路径拼接，生成完整路径并添加到jsRealPaths中
            for jsFileName in jsFileNames:
                jsFileName = base_url + jsFileName
                jsRealPaths.append(jsFileName)

        # 如果jsUrlpath中不包含"§§§"，表示这是通过异步加载的JS文件
        else:
            # 将路径按"/"分割成列表，并删除最后一部分（通常是文件名）
            tmpUrl = jsUrlpath.split("/")
            del tmpUrl[-1]
            
            # 拼接剩余部分，形成基础路径，并在末尾添加"/"
            base_url = "/".join(tmpUrl) + "/"
            
            # 遍历jsFileNames列表，使用Utils类的getFilename方法提取文件名，并与基础路径拼接
            for jsFileName in jsFileNames:
                jsFileName = Utils().getFilename(jsFileName)  # 提取文件名
                jsFileName = base_url + jsFileName  # 拼接完整路径
                jsRealPaths.append(jsFileName)  # 添加到jsRealPaths列表中

        # 尝试块：处理下载逻辑
        try:
            # 获取解析后的域名部分
            domain = resForDB.netloc
            
            # 如果域名中包含端口号（":"），将其替换为"_"
            if ":" in domain:
                domain = str(domain).replace(":", "_")
            
            # 调用DownloadJs类的downloadJs方法，下载JS文件
            DownloadJs(jsRealPaths, self.options).downloadJs(self.projectTag, domain, jsSplitId)
            
            # 记录日志，表明downjs功能正常运行
            self.log.debug("downjs功能正常")

        # 异常处理：如果发生异常，记录错误日志
        except Exception as e:
            self.log.error("[Err] %s" % e)

    def checkSpiltingTwice(self, projectPath):
        self.log.info(Utils().tellTime() + "正在暴力检测JS文件中...")
        for parent, dirnames, filenames in os.walk(projectPath, followlinks=True):
            for filename in filenames:
                if filename != self.projectTag + ".db":
                    tmpName = filename.split(".")
                    if len(tmpName) == 4:
                        localFileName = "." + tmpName[-2] + ".js"
                        self.localFileNames.append(localFileName)
                        remotePath = DatabaseType(self.projectTag).getJsUrlFromDB(filename, projectPath)
                        tmpRemotePath = remotePath.split("/")
                        del tmpRemotePath[-1]
                        newRemotePath = "/".join(tmpRemotePath) + "/"
                        self.remotePaths.append(newRemotePath)
        self.remotePaths = list(set(self.remotePaths))
        if len(self.localFileNames) > 3:  # 一切随缘
            localFileName = self.localFileNames[0]
            for baseurl in self.remotePaths:
                tmpRemoteFileURLs = []
                res = urlparse(baseurl)
                i = 0
                while i < 500:
                    remoteFileURL = baseurl + str(i) + localFileName
                    i = i + 1
                    tmpRemoteFileURLs.append(remoteFileURL)
                GroupBy(tmpRemoteFileURLs,self.options).stat()
                tmpRemoteFileURLs = GroupBy(tmpRemoteFileURLs,self.options).start()
                for remoteFileURL in tmpRemoteFileURLs:
                    self.remoteFileURLs.append(remoteFileURL)
        else:
            for localFileName in self.localFileNames:
                for baseurl in self.remotePaths:
                    tmpRemoteFileURLs = []
                    res = urlparse(baseurl)
                    i = 0
                    while i < 500:
                        remoteFileURL = baseurl + str(i) + localFileName
                        i = i + 1
                        tmpRemoteFileURLs.append(remoteFileURL)
                    GroupBy(tmpRemoteFileURLs,self.options).stat()
                    tmpRemoteFileURLs = GroupBy(tmpRemoteFileURLs,self.options).start()
                    for remoteFileURL in tmpRemoteFileURLs:
                        self.remoteFileURLs.append(remoteFileURL)
        if self.remoteFileURLs != []:
            domain = res.netloc
            if ":" in domain:
                domain = str(domain).replace(":", "_") #处理端口号
            self.remoteFileURLs = list(set(self.remoteFileURLs))  # 其实不会重复
            self.log.info(Utils().tellTime() + "暴力检测结束，成功检测出" + str(len(self.remoteFileURLs)) + "个JS文件")
            DownloadJs(self.remoteFileURLs,self.options).downloadJs(self.projectTag, domain, 999)  # 999表示爆破

    def recoverStart(self):
        projectPath = DatabaseType(self.projectTag).getPathfromDB()
        for parent, dirnames, filenames in os.walk(projectPath, followlinks=True):
            for filename in filenames:
                if filename != self.projectTag + ".db":
                    filePath = os.path.join(parent, filename)
                    self.checkCodeSpilting(filePath)
        try:
            self.checkSpiltingTwice(projectPath)
            self.log.debug("checkSpiltingTwice模块正常")
        except Exception as e:
            self.log.error("[Err] %s" % e)

