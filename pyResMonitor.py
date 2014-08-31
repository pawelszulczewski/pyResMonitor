#!/usr/bin/env python
# -*- coding: utf-8 -*-

# pyResMonitor
# psz, 2014, <pawel(at)szulczewski(dot)org>
# GNU/GPL v3+

import getopt, md5, os, smtplib
from time import strftime
from socket import gethostname
from sys import argv, exit

# exit codes
__WRONG_PARAM_ERROR  = 2            # wrong parameter
__NO_CONF_FILE_ERROR = 3            # no config file
__LOADAVG_FILE_ERROR = 101          # problem with /proc/loadavg
__MEMORY_FILE_ERROR  = 102          # problem with /proc/meminfo
__MTAB_FILE_ERROR    = 103          # problem with /etc/mtab

# files
__LOAD_FILE = "/proc/loadavg"       # file with current load
__MEM_FILE  = "/proc/meminfo"       # file with memory
__MTAB_FILE = "/etc/mtab"           # currently mounted volumens
__DIGE_FILE = "/tmp/smpresdigest"   # file with last md5 hash

__HOSTNAME = gethostname().upper()  # hostname

# flags and lists
conf_defaults = 0
conf_hdd_excluded = 0
fs_defaults = {}
fs_excluded = []
mounted_fs = {}                     # dictionary of mounted volumes
                                    # key: filesystem (/home), value: % of occupied
                                    # disk space

files = {}                          # dictionary of files

# globals
global hdd_default_min_percent
fs_default_min_percent = 0.0
global load_default_value
load_default_value = 0.0
global swap_min_percent
swap_min_percent = 0.0
global mem_min_percent
mem_min_percent = 0.0
global email_addrs

# returns size in human-readable units
def get_human_bytes(_bytes):
    for x in ['bytes','KiB','MiB','GiB']:
        if _bytes < 1024.0:
            return "%3.1f %s" % (_bytes, x)
        _bytes /= 1024.0

# returns number of bytes from _string where _string ends on K, M or G
def get_bytes (_string):
    last_c = _string [-1]
    s_wout_last = _string[:-1]
    if (s_wout_last.isdigit()):
        value = int (s_wout_last)
    else:
        return -1

    if last_c.upper() == 'K':
        powrbase = 1
    elif last_c.upper() == 'M':
        powrbase = 2
    elif last_c.upper() == 'G':
        powrbase = 3
    else:
        powrbase = 0
        if (_string.isdigit()):
            value = int (_string)
        else:
            return -1
    return value * (1024 ** powrbase)

# returns MD5 checksum from _string
def get_md5_digest (_string):
    m = md5.new()
    m.update(_string)
    return m.hexdigest()

# checks checksum from the _file
def check_md5_digest (_file):
    if os.path.isfile(_file):
        with open(_file, 'r') as f:
            md5_hash = f.read()        
        f.close()
        return md5_hash
    else:
        return ''

# writes checksum _md5_hash to _file
def update_md5_digest (_file, _md5_hash):
    with open(_file, 'w') as f:        
        f.write(_md5_hash)
    f.close()
 
# this checks system and sends report
def check_system_and_send_report ():
    report=""

    # load
    current_load = check_load()
    if (load_default_value > 0.0) and (current_load >= load_default_value):
        report += "* [loa]\tload\t{0}\n".format(current_load, load_default_value)

    # RAM / swap
    if (swap_min_percent > 0.0) or (mem_min_percent > 0.0):
        check_memory()
    if (swap_min_percent > 0.0) and (swap_prct_act >= swap_min_percent):
        report += "* [mem]\tswap\t{0}%\tused\n".format(swap_prct_act, swap_min_percent)
    if (mem_min_percent > 0.0) and (mem_prct_act >= mem_min_percent):
        report += "* [mem]\tmem\t{0}%\tused\n".format(mem_prct_act, mem_min_percent)

    # volumes -------------------------------->
    if len(mounted_fs) > 0:
        for k in mounted_fs.keys():
            if fs_excluded.count(k) > 0:        # excluding listed in FS_EXCLUDED
                mounted_fs.pop(k)
                continue
            elif fs_defaults.has_key(k) > 0:
                if float(mounted_fs[k]) <= float(fs_defaults[k]):
                    mounted_fs.pop(k)
                    continue
            elif float(mounted_fs[k]) <= float(fs_default_min_percent):
                mounted_fs.pop(k)
                continue
    if len(mounted_fs) > 0:        
        for k in mounted_fs.keys():
            report += "* [hdd]\t{0}\t{1}%\tused\n".format(k, mounted_fs[k])
    # <-------------------------------- volumes

    # files ----------------------------------->
    if len(files) > 0:
        for f in files.keys():
            current_file_size = get_file_size(f)
            if current_file_size <= files[f]:
                files.pop(f)
                continue
    if len(files) > 0:
        for f in files.keys():
            report += "* [fil]\t{0}\texceeds {1}\n".format(f, get_human_bytes(files[f]))
    # <----------------------------------- files

    # sending report (it it's different than last one)
    if len(report) > 0:
        md5_from_file = check_md5_digest (__DIGE_FILE)
        md5_from_repo = get_md5_digest (report)
        if (md5_from_file != md5_from_repo):
            update_md5_digest(__DIGE_FILE, md5_from_repo)
            curr_host_date_time = __HOSTNAME + " " + strftime("%Y-%m-%d %H:%M:%S")
            header = '-' * len(curr_host_date_time) + '\n'
            header += curr_host_date_time + '\n'
            header += '-' * len(curr_host_date_time) + '\n'
            report_with_subj = "Subject: {0}\n".format("ATTENTION! " + __HOSTNAME) + header + report
            from_addr = "foo"
            to_addrs = email_addrs.split(";")
            username = "your_email_username"
            password = "your_user_password"
            server = smtplib.SMTP('your_smtp_host')
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr, to_addrs, report_with_subj)
            server.quit()

# this reads the configuration file
def read_conf_file (_file):
    check_filesystems = 0
    try:
        f = open(_file, 'r')
    except IOError as e:
        print str(e)
        exit(__NO_CONF_FILE_ERROR)
    for line in f:
        if line.startswith('[FS]'):
            conf_defaults = 1
            conf_hdd_excluded = 0
            conf_files = 0
        elif line.startswith('[FS_EXCLUDED]'):
            conf_defaults = 0
            conf_hdd_excluded = 1
            conf_files = 0
        elif line.startswith('[FILES]'):
            conf_defaults = 0
            conf_hdd_excluded = 0
            conf_files = 1
        elif line.startswith('email_addrs'):
            global email_addrs
            email_addrs = line.split("=", 1)[1].rstrip()
        elif line.startswith('fs_default_min_percent'):
            global fs_default_min_percent
            fs_default_min_percent = float(line.split("=", 1)[1].rstrip())
            if fs_default_min_percent > 0:
                check_filesystems = 1
        elif line.startswith('load_default_value'):
            global load_default_value
            load_default_value = float(line.split("=", 1)[1].rstrip())
        elif line.startswith('swap_min_percent'):
            global swap_min_percent
            swap_min_percent = float(line.split("=", 1)[1].rstrip())
        elif line.startswith('mem_min_percent'):
            global mem_min_percent
            mem_min_percent = float(line.split("=", 1)[1].rstrip())

        # volumes
        if line.startswith('/') and conf_defaults == 1:
            device = line.split("=", 1)[0].rstrip()
            device_prct = line.split("=", 1)[1].rstrip()
            if device_prct > 0:
                fs_defaults[device] = device_prct
                check_filesystems = 1

        # excluding some volumes
        elif line.startswith('/') and conf_hdd_excluded == 1:
            exclude_device = line.split("=", 1)[0].rstrip()
            fs_excluded.append(exclude_device)

        # list of files
        elif line.startswith('/') and conf_files == 1:
            file2check = line.split("=", 1)[0].rstrip()   # nazwa pliku
            filevalue = line.split("=", 1)[1].rstrip()    # wielkość pliku (z pliku konf)
            filevalue_in_bytes = get_bytes (filevalue)    # wielkość w bajtach
            if (filevalue_in_bytes != -1):
                files[file2check] = filevalue_in_bytes

    # check mounted volumens (if neccesary)
    if check_filesystems > 0:        
        check_volumes()
    f.close()

# usage
def usage():
    print "\npyResMonitor [option] [config_file]"
    print "\nsimply resource monitor (load, memmory, hdd)"
    print "\n\toption\n\t\t-h, --help\t\tusage"
    print "\t\t-c, --config [config_file]\tconfiguration file\n"

# returns the size of _file (in bytes). If file not found -- returns -1
def get_file_size (_file):
    if (os.path.isfile(_file)):
        file_size = os.path.getsize(_file)
    else:
        file_size = -1
    return file_size

# returns the percent of used mounted volume
def get_fs_free_space (_device):
    stat = os.statvfs(_device)
    free_blocks = float (stat.f_bavail)
    total_blocks = float (stat.f_blocks)
    if total_blocks > 0:
        free_blocks_percent = round ((total_blocks - free_blocks) / total_blocks * 100, 2)
    else: 
        free_blocks_percent = -1
    return free_blocks_percent

# returns load (from last minute)
def check_load():
    try:
        f = open(__LOAD_FILE, 'r')
    except IOError as e:
        print str(e) 
        exit(__LOADAVG_FILE_ERROR)    
    line = f.readline()
    load_value = float(line.split(' ', 1)[0].rstrip())
    f.close()
    return load_value
    
# returns the percent of used memory (RAM and swap)
def check_memory():
    try:
        f = open(__MEM_FILE, 'r')
    except IOError as e:
        print str(e)
        exit(__MEMORY_FILE_ERROR)
    for line in f:
        if "SwapTotal" in line:
            swap_total = float (line.split(' ', 1)[1].strip().split(' ', 1)[0])
        elif "SwapFree" in line:
            swap_free = float (line.split(' ', 1)[1].strip().split(' ', 1)[0])
        elif "MemTotal" in line:
            mem_total = float (line.split(' ', 1)[1].strip().split(' ', 1)[0])
        elif "MemFree" in line:
            mem_free = float (line.split(' ', 1)[1].strip().split(' ', 1)[0])
    global mem_prct_act
    if mem_total > 0:
        mem_prct_act = round ((mem_total - mem_free) / mem_total * 100, 2)
    else:
        mem_prct_act = -1
    global swap_prct_act
    if swap_total > 0:
        swap_prct_act = round ((swap_total - swap_free) / swap_total * 100, 2)
    else:
        swap_prct_act = -1
    f.close()    

# checks mounted volumes
def check_volumes():
    try:
        f = open(__MTAB_FILE, 'r')
    except IOError as e:
        print str(e)
        exit(__MTAB_FILE_ERROR)
    for line in f:
        mounted = line.split(' ', 1)[1].strip().split(' ', 1)[0]
        free_space = get_fs_free_space(mounted)
        if free_space >= 0:
            mounted_fs[mounted] = free_space
    f.close()
    
def main ():
    try:
        opts, args = getopt.getopt(argv[1:], "hc:", ["help", "config="])    
    except getopt.GetoptError:
        usage()
        exit(__WRONG_PARAM_ERROR)
    if len(opts) == 0:
        usage()
        exit(__WRONG_PARAM_ERROR)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            exit()
        elif opt in ("-c", "--config"):
            read_conf_file(arg)            # reading configuration file
            check_system_and_send_report()
                    
if __name__ == "__main__" :
    main () 
