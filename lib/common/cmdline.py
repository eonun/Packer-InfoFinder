# !/usr/bin/env python3
# -*- encoding: utf-8 -*-

import optparse,sys


class CommandLines():

    def cmd(self):
        parse = optparse.OptionParser()
        parse.add_option('-u', '--url', dest='url', help='请输入目标 URL')
        parse.add_option('-c', '--cookie', dest='cookie', help='请输入网站 Cookies')
        parse.add_option('-d', '--head', dest='head', default='Cache-Control:no-cache', help='请输入额外的 HTTP 头')
        parse.add_option('-l', '--list', dest='list', help='请输入目标 URL 列表文件')
        parse.add_option('-p', '--proxy', dest='proxy', type=str, help='请输入代理地址')
        # parse.add_option('-j', '--js', dest='js', type=str, help='Extra JS Files')
        parse.add_option('-b', '--base', dest='baseurl', type=str, help='请输入 baseurl')
        parse.add_option('-r', '--report', dest='report', default='html,doc', type=str, help='请选择报告类型')
        parse.add_option('-f', '--flag', dest='ssl_flag', default='1', type=str, help='SSL 安全标志')
        parse.add_option('-s', '--silent', dest='silent', type=str, help='静默模式（自定义报告名称）')
        (options, args) = parse.parse_args()
        if options.list == None:
            if options.url == None:
                parse.print_help()
                sys.exit(0)
        return options


if __name__ == '__main__':
    print(CommandLines().cmd().cookie)
