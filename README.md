pyResMonitor
============
This is a simple system resources monitor. It monitors load, mounted
volumes and memory (both RAM and swap) and files.
Sends email with report if some of the value exceeds value set in the configuration file.

Syntax
------
pyResMonitor [option] [config_file]
	     option
		-h, --help			short help<return>
		-c, --config [config_file]	configuration file

Configuration file
------------------
**[DEFAULTS]**
- mail_addrs=[LISTA] - email addresses (separated by semicolons), the report will be send to this emails,
- fs_default_min_percent=[REAL] - default acceptable percent of used (any) mounted filesystem,
- load_default_value=[REAL] - maximum acceptable load value,
- swap_min_percent=[REAL] - maximum acceptable percent of used swap memmory,
- mem_min_percent=[REAL] - maximum acceptable percent of used RAM memmory
**[FS]**
- [FS]=[REAL] - percent of used mounted filsystem [FS], it appends the fs_default_min_percent value for this filesystem,
**[FILES]**
- [FILE]=[INT] { ,K,M,G} - max file size of [FILE]. If handles K (for kibibytes), M (for mebibytes) and G (for gibibytes). For example /home/user/file.txt=20000 means that file cannot exceed 20000 bytes, /home/user/file.txt=14K means file cannot exceed 14 KiB and so on,
**[FS_EXCLUDED]**
- list of mounted volumens to be ignored
