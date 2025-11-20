import numpy as np
import subprocess
import os

BSIZE_SP = 512 # Max size of a line of data; we don't want to read the
               # whole file to find a line, in case file does not have
               # expected structure.
MDATA_LIST = [b'title', b'date', b'plotname', b'flags', b'no. variables',
              b'no. points', b'dimensions', b'command', b'option']


class NgSim:
    def __init__(self, netlist_file,working_folder,verbose=True):
        """
        初始化类，设置网表文件、兼容性类型和工作文件夹路径。
        """
        self.verbose = verbose
        self.working_folder = working_folder
        self.netlist_file = netlist_file
        with open(netlist_file, 'r') as infile:
            self.netlist_lines = infile.readlines()
        
        self.include_list = []
        self.dot_command_list = []
        self.component_changes_dict = {}
        self.component_delete_list = []
        self.compat_type = "ltpsa"

    def setup_working_dir(self):
        if not os.path.exists(self.working_folder):
            os.makedirs(self.working_folder)

        spiceinit_file = os.path.join(self.working_folder, ".spiceinit")
        with open(spiceinit_file, 'w') as f:
            f.write("set ngbehavior="+self.compat_type+"\n")

        # 创建新文件并准备写入
        new_netlist_file = os.path.join(self.working_folder, self.netlist_file)  # 新的网表文件
        with open(new_netlist_file, 'w') as outfile:
            dot_command_added = False  # 标志变量，判断是否添加了仿真命令

            for line in self.netlist_lines:
                # 去掉行首的空格后，检查第一个字符是否为 '.' 或 '*'
                line = line.lstrip()  # 去除行首空格
                if not line or line[0] == "*":
                    continue
                elif line[0] !="." :
                    if not dot_command_added:
                        for include_line in self.include_list:
                            outfile.write(include_line + "\n")
                        for command in self.dot_command_list:
                            outfile.write(command + "\n")
                        dot_command_added = True

                    parts = line.split()

                    # 判断第一个元件名称是否需要替换或者删除
                    component_name = parts[0].lower()  # 将元件名转为小写

                    # 如果需要删除直接跳过
                    if component_name in self.component_delete_list:
                        continue
                    # 如果需要替换元件值
                    elif component_name in self.component_changes_dict:
                        # 修改最后部分的值为新的元件值
                        parts[-1] = self.component_changes_dict[component_name]
                        
                        # 重新构建修改后的行
                        line = " ".join(parts)+"\n"

                # 写入每一行
                outfile.write(line)

    def add_include(self,include_file):
        include_file = include_file.strip()
        if include_file[0] != '.' and include_file[0:7] == 'include':
            include_file = '.'+include_file
        elif include_file[0:8] != '.include':
            include_file = '.include "' + include_file + '"'
        self.include_list.append(include_file)

    def clear_include(self):
        self.include_list = []

    def add_dot_command(self,dot_command):
        dot_command = dot_command.lower().strip()
        if dot_command[0] != '.':
            dot_command = '.'+dot_command
        self.dot_command_list.append(dot_command)

    def clear_dot_command(self):
        self.dot_command_list = []

    def add_mod_comp(self,comp,value):
        """
        修改网表文件：增加一个下次run要替换的元件值到更改列表中
        """
        self.component_changes_dict[comp.lower()] = value

    def clear_mod_comp(self):
        """
        清空修改字典：之前add的要修改内容都会被清空
        """
        self.component_changes_dict = {}

    def add_delete_comp(self,comp):
        self.component_delete_list.append(comp)

    def clear_delete_comp(self):
        self.component_delete_list = []

    def run(self):
        """
        运行仿真命令（ngspice），并捕获输出。
        """
        self.setup_working_dir()
        # 执行命令并捕获标准输出和标准错误信息
        command = f"ngspice -r out.raw -b {self.netlist_file}"
        result = subprocess.run(command, shell=True, cwd=self.working_folder, capture_output=True, text=True)

        # 检查命令是否成功执行
        if result.returncode == 0:
            if self.verbose == True:
                print("Simulation executed successfully.")
            # 读取仿真结果文件
            raw_file_path = os.path.join(self.working_folder, "out.raw")
            if os.path.exists(raw_file_path):
                return self.rawread(raw_file_path)
        else:
            # 打印标准输出和标准错误信息
            print("Standard Output:", result.stdout)
            print("Standard Error:", result.stderr)
            raise ValueError(f"Simulation failed with return code {result.returncode}")

    def rawread(self,fname: str):
        """Read ngspice binary raw files. Return tuple of the data, and the
        plot metadata. The dtype of the data contains field names. This is
        not very robust yet, and only supports ngspice.
        >>> darr, mdata = rawread('test.py')
        >>> darr.dtype.names
        >>> plot(np.real(darr['frequency']), np.abs(darr['v(out)']))
        """
        # Example header of raw file
        # Title: rc band pass example circuit
        # Date: Sun Feb 21 11:29:14  2016
        # Plotname: AC Analysis
        # Flags: complex
        # No. Variables: 3
        # No. Points: 41
        # Variables:
        #         0       frequency       frequency       grid=3
        #         1       v(out)  voltage
        #         2       v(in)   voltage
        # Binary:
        fp = open(fname, 'rb')
        count = 0
        arrs = []
        plots = []
        plot = {}
        while (True):
            try:
                mdata = fp.readline(BSIZE_SP).split(b':', maxsplit=1)
            except:
                raise ValueError(f"failed at 'mdata = fp.readline(BSIZE_SP).split(b':', maxsplit=1)'")
            if len(mdata) == 2:
                if mdata[0].lower() in MDATA_LIST:
                    plot[mdata[0].lower()] = mdata[1].strip()
                if mdata[0].lower() == b'variables':
                    nvars = int(plot[b'no. variables'])
                    npoints = int(plot[b'no. points'])
                    plot['varnames'] = []
                    plot['varunits'] = []
                    for varn in range(nvars):
                        varspec = (fp.readline(BSIZE_SP).strip()
                                   .decode('ascii').split())
                        assert(varn == int(varspec[0]))
                        plot['varnames'].append(varspec[1])
                        plot['varunits'].append(varspec[2])
                if mdata[0].lower() == b'binary':
                    rowdtype = np.dtype({'names': plot['varnames'],
                                         'formats': [np.complex128 if b'complex'
                                                     in plot[b'flags']
                                                     else np.float64]*nvars})
                    # We should have all the metadata by now
                    arrs.append(np.fromfile(fp, dtype=rowdtype, count=npoints))
                    plots.append(plot)
                    plot = {} # reset the plot dict
                    fp.readline() # Read to the end of line
            else:
                break
        return arrs, plots

#if __name__ == '__main__':
   #arrs, plots = rawread('test.raw')
   #print(arrs)
