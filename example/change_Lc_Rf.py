# 对于特定反馈电感Lf型号，改变补偿电感Lc，寻找使得带宽变为1MHz的反馈电阻Rf，观察带宽均为1MHz时补偿电感与反馈电阻的关系：
import numpy as np
import argparse
from pyng import NgSim
import pickle
import matplotlib.pyplot as plt
from rich.progress import Progress,TimeElapsedColumn
import os

# 参数设置

# 仿真类型所用到的基本参数
sim_freq_low = 18
sim_freq_high = 22
dot_distribution = "lin 10000"

# 要仿真的反馈电感模型
#Lf_dict = {'1812cs472':4.7,'1812cs562':5.6,'1812cs682':6.8,'1812cs822':8.2,'1812cs103':10} # 器件编号：电感值（uH）
Lf_dict = {'1812cs103':10,'1812cs123':12,'1812cs153':15,'1812cs183':18,'1812cs223':22,'1812cs273':27,'1812cs333':33,} # 器件编号：电感值（uH）
#Lf_dict = {'1812cs333':33,'1812cs223':22,'1812cs273':27,} # 器件编号：电感值（uH）
#Lf_dict = {'1812cs333':33,} # 器件编号：电感值（uH）
#Lf_dict = {'1812cs333':33,'1812ls333':33,'1812ls393':39,'1812ls473':47,'1812ls563':56,} # 器件编号：电感值（uH）
#Lf_dict = {'1812ls563':56} # 器件编号：电感值（uH）

# 设置搜索反馈电容相关的参数
target_peak_freq = 20e6
max_Cf_search_round = 20 # 搜索Cf时最大搜索轮数
Lc_Cf_search_str = "1.5u" # 搜索Cf的时候固定的Lc的值，理论20MHz对应1.36uH，但仿真表明取大一点影响更小，适用电感型号更多
peak_precision = 1/500   # 带宽精度
minimum_Cf = 0.01 # 在找不到大于目标带宽的Cf时保障Cf不小于这个最小值
maximum_Cf = 100 # 在找不到小于目标带宽的Cf时保障Cf不大于这个最小值

# 设置要仿真的补偿电感范围
Lc_low = 1.25
Lc_high = 1.56
Lc_delta = 0.005
#Lc_low = 1.38
#Lc_high = 1.42
#Lc_delta = 0.005

# 设置要搜索的反馈电阻相关参数
target_bandwidth = 1e6
max_Rf_search_round = 10 # 搜索Rf时最大搜索轮数
Rf_start = 50       # 初始测试电阻大小：单位kOhm
bandwidth_precision = 1/100   # 带宽精度
minimum_Rf = 1 # 在找不到大于目标带宽的Rf时保障Rf不小于这个最小值
maximum_Rf = 1000 # 在找不到小于目标带宽的Rf时保障Rf不大于这个最小值

def sim():
    ########################################
    # 开始进行仿真运算
    ########################################

    ns = NgSim("idealC_1812cs103_compensate_idealL.cir","ngspice_working_folder",verbose=False)
    data = {}
    Lc_list = np.arange(Lc_low,Lc_high,Lc_delta)
    # 初始化进度条
    with Progress(*Progress.get_default_columns(),TimeElapsedColumn(),) as progress:
        task = progress.add_task("[cyan]Processing...", total=len(Lf_dict)*(max_Cf_search_round+len(Lc_list)*max_Rf_search_round))

        # 对多个不同型号的反馈电感进行试验
        for Lf_name in Lf_dict:

            # 相关数据的存储
            Lf_data = {}
            Lf_data['Lc_list'] = Lc_list
            Lf_data['Cf_value'] = 0
            Lf_data['optimal_Cf'] = False
            # 增益相关数据存储
            Lf_data['peak_value_ramp_list'] =[]
            Lf_data['peak_value_rf_list'] =[]
            Lf_data['optimal_Rf_list'] =[]
            Lf_data['f_peak_ramp_list']     =[]
            Lf_data['f_low_ramp_list']      =[]
            Lf_data['f_high_ramp_list']     =[]
            Lf_data['bandwidth_ramp_list']    =[]
            Lf_data['ramp_valid_list']      =[]  # 存储相关数据是否有效
            # 噪声相关数据存储
            Lf_data['out_noise_at_sig_peak_list'] = []
            # 是否自激数据存储
            Lf_data['sim_stable_list'] = []

            # 添加要include进去可能使用的反馈电感模型
            ns.clear_include()
            current_dir = os.path.dirname(os.path.abspath(__file__))
            components_dir = os.path.join(current_dir, 'components')
            ns.add_include(os.path.join(components_dir, Lf_name + '.cir'))
            ns.add_include(os.path.join(components_dir, 'ada4817.cir'))
            Lf_value = Lf_dict[Lf_name]          # 电感数值以uH为单位
            # 设置用于寻找合适的电感和带宽的仿真类型
            ns.clear_dot_command()
            ns.add_dot_command("ac " + dot_distribution + " " + \
                    str(sim_freq_low) + "Meg " + str(sim_freq_high) +"Meg") # 查找带宽和增益，进行ac仿真
            
            # 搜索获取最佳电容值之后固定电容值进行后续实验
            print(f"for {Lf_name}，searching optimal Cf:")
            Cf = 1/(np.pow((2*np.pi*20e6),2)*Lf_value*1e-6)*1e12 # 电容数值以pF为单位，一开始的搜索值取理论值
            round_count = 0
            optimal_Cf = False # 用于记录Cf的寻找是否找到了最优值
            Cf_top = 0
            Cf_btm = 0
            peak_freq_top = 1e8
            peak_freq_btm =0
            while True:
                round_count +=1
                ns.clear_mod_comp()
                # 更改反馈电感为特定模型
                ns.add_mod_comp("xl1",Lf_name)
                # 更改反馈电容的值为理论所需的电容值
                Cf_str = np.format_float_positional(Cf,precision=2,unique=False) + 'p'
                ns.add_mod_comp("c2",Cf_str)
                # 更改补偿电阻
                ns.add_mod_comp("l2",Lc_Cf_search_str) # 搜索Cf的时候固定Lc的值
                # 更改划分找到的反馈电阻
                Rf_str = np.format_float_positional(Rf_start,precision=2,unique=False) + 'k' # 电阻数值以kOhm为单位，保留两位小数，和下面求解Rf的过程保持一致；搜索Cf时使用Rf搜索开始值
                ns.add_mod_comp("r2",Rf_str)

                arrs,plots = ns.run()

                ###############################
                # 在划分搜索过程中取出以下数据：
                # 增益峰值
                ###############################
                # 首先取出增益相关参数 #
                freq = np.real(arrs[0]['frequency'])
                vout = arrs[0]['v(out)']
                iin = arrs[0]['i(v5)']
                ramp = np.abs(vout)/np.abs(iin)
                # 找到峰值
                peak_freq_ramp = freq[np.argmax(ramp)]
                print(f"At round {round_count}, Cf of {np.format_float_positional(Cf,precision=2,unique=False)} pF has a peak at {np.format_float_positional(peak_freq_ramp/1e6,precision=4)} MHz;")
                # 更新一下进度条
                progress.update(task, advance=1)

                # 通过目前找到的大于目标频率的最小频率、小于目标频率的最大频率以及本次测试频率的关系来更改下一次测试的Cf值
                # 存在两种情况：
                # 1. 还未找到大于或小于目标频率的频率，使用固定方向的搜索，步长可以调整
                #       - 一开始因为没有上下界，所以第一次搜索一定找到一个界，而后就往另一个方向搜索，必定频率也一个方向变化，这是由反馈电阻和频率的确定的负相关关系决定的，如果这个负相关因为特定原因不满足，那么这里的搜索可能无效
                #       - 固定方向搜索的时候可以有搜索快慢，如果得到的频率结果已经很接近，就用小步长搜索上下界
                # 2. 已经找到大于和小于目标频率的频率，那么通过在中间某个位置取新的Cf值，逐渐逼近
                #       - 取值方法可以用二分法，也可以结合已知的频率关系按照比例取Cf
                # 3. 如果找到了足够接近的上下界，就取其中的上界对应的电阻
                delta_Cf = Cf/2 # 固定方向搜索步长与当前Cf成比例
                if np.abs(peak_freq_ramp -target_peak_freq) < target_peak_freq / 100: # 在一开始就足够接近目标频率的时候让delta_Cf快速衰减
                    delta_Cf = delta_Cf / 5 
                elif np.abs(peak_freq_ramp -target_peak_freq) < target_peak_freq / 50:
                    delta_Cf = delta_Cf / 2

                if peak_freq_ramp >= target_peak_freq:
                    peak_freq_top = peak_freq_ramp
                    Cf_top = Cf
                    if Cf_btm == 0:# 仅找到上界，使用固定大小搜索
                        Cf = round(Cf + delta_Cf,2)
                    else:          # 已经找到上下界，使用划分法搜索
                        Cf = round(((target_peak_freq - peak_freq_btm)/(peak_freq_top-peak_freq_btm)*(Cf_top-Cf_btm)+Cf_btm)*2/3 + (Cf_top+Cf_btm)/2/3,2) # 保留两位小数，和写到spice网表中的保持一致
                elif peak_freq_ramp < target_peak_freq:
                    peak_freq_btm = peak_freq_ramp
                    Cf_btm = Cf
                    if Cf_top == 0:# 仅找到下界，使用固定大小搜索
                        Cf = round(Cf - delta_Cf,2)
                    else:          # 已经找到上下界，使用划分法搜索
                        Cf = round(((target_peak_freq - peak_freq_btm)/(peak_freq_top-peak_freq_btm)*(Cf_top-Cf_btm)+Cf_btm)*2/3 + (Cf_top+Cf_btm)/2/3,2) # 保留两位小数，和写到spice网表中的保持一致

                if peak_freq_top - target_peak_freq < target_peak_freq*peak_precision:
                    Cf = Cf_top
                    peak_freq_ramp = peak_freq_top
                    print(f"Found optimal Cf of {np.format_float_positional(Cf,precision=2,unique=False)} pF with peak at {np.format_float_positional(peak_freq_ramp/1e6,precision=4)} MHz.")
                    progress.update(task,advance = max_Cf_search_round - round_count)
                    optimal_Cf = True
                    break

                # 对于Cf超过上下界的情况，直接退出
                if Cf > maximum_Cf:
                    Cf = Cf_top
                    peak_freq_ramp = peak_freq_top
                    progress.update(task,advance = max_Cf_search_round - round_count)
                    print(f"At round {round_count} found Cf of {np.format_float_positional(Cf,precision=2,unique=False)} pF with peak at {np.format_float_positional(peak_freq_ramp/1e6,precision=4)} MHz.")
                    break
                elif Cf <= minimum_Cf:
                    Cf = Cf_btm
                    peak_freq_ramp = peak_freq_btm
                    progress.update(task,advance = max_Cf_search_round - round_count)
                    print(f"At round {round_count} found Cf of {np.format_float_positional(Cf,precision=2,unique=False)} pF with peak at {np.format_float_positional(peak_freq_ramp/1e6,precision=4)} MHz.")
                    break

                # 对于计算太多轮次的就不计算了
                if round_count >= max_Cf_search_round:
                    if Cf_top != 0:
                        Cf = Cf_top
                        peak_freq_ramp = peak_freq_top
                    print(f"At round {round_count} found Cf of {np.format_float_positional(Cf,precision=2,unique=False)} pF with peak at {np.format_float_positional(peak_freq_ramp/1e6,precision=4)} MHz.")
                    break
            # 记录下找到的Cf数据
            Lf_data['Cf_value'] = Cf
            Lf_data['optimal_Cf'] = optimal_Cf


            ##########################################################
            # 开始改变补偿电感进行仿真
            #
            # 对于同一个反馈电感型号改变补偿电感Lc时，从上一个Lc搜索到的理想电阻值开始搜索会更加快，因此在Lc循环外进行Rf初始化比较理想
            Rf=Rf_start
            for Lc in Lc_list:
                Lc_str = np.format_float_positional(Lc,precision=4,unique=False) + 'u' # 电感数值以uH为单位
                print(f"for {Lf_name} with compensation L {Lc_str}:")

                #############################################
                # 使用划分法查找最接近1MHz带宽的反馈电阻大小
                round_count = 0 # 用于记录轮数，可以将轮数太多算不到的提前停止
                optimal_Rf = False # 用于记录Rf的寻找是否找到了最优值
                Rf_top = 0
                Rf_btm = 0
                bandwidth_top = 1e7
                bandwidth_btm =0
                while True:
                    round_count +=1
                    # 设置用于寻找合适的电感和带宽的仿真类型
                    ns.clear_dot_command()
                    ns.add_dot_command("ac " + dot_distribution + " " + \
                            str(sim_freq_low) + "Meg " + str(sim_freq_high) +"Meg") # 查找带宽和增益，进行ac仿真
                    ns.clear_mod_comp()
                    # 更改反馈电感为特定模型
                    ns.add_mod_comp("xl1",Lf_name)
                    # 更改反馈电容的值为理论所需的电容值
                    ns.add_mod_comp("c2",Cf_str)
                    # 更改补偿电阻
                    ns.add_mod_comp("l2",Lc_str)
                    # 更改划分找到的反馈电阻
                    Rf_str = np.format_float_positional(Rf,precision=2,unique=False) + 'k' # 电阻数值以kOhm为单位，保留两位小数，和下面求解Rf的过程保持一致
                    ns.add_mod_comp("r2",Rf_str)

                    arrs,plots = ns.run()

                    ###############################
                    # 在划分过程中取出以下数据：
                    # 1. 增益峰值、增益带宽、增益峰值位置
                    ###############################

                    # 首先取出增益相关参数 #
                    freq = np.real(arrs[0]['frequency'])
                    vout = arrs[0]['v(out)']
                    iin = arrs[0]['i(v5)']

                    ramp = np.abs(vout)/np.abs(iin)

                    # 找到峰值
                    peak_value_ramp = np.max(ramp)

                    # 计算 -3 dB 对应的幅度（即 1/√2 的幅度）
                    half_peak_value_ramp = peak_value_ramp / np.sqrt(2)

                    # 查找降到 -3 dB 的频率
                    # 使用 numpy 的 where 找到所有满足幅度条件的位置
                    indices_above_half_peak_ramp = np.where(ramp >= half_peak_value_ramp)[0]

                    ramp_valid = False # 用来表征找到的带宽是否是真实带宽而非仿真频率宽度不够导致的带宽的情况
                    # 计算带宽 Δf，即找到最小和最大频率点
                    if len(indices_above_half_peak_ramp) >= 2:
                        f_low_ramp = freq[indices_above_half_peak_ramp[0]]
                        f_high_ramp = freq[indices_above_half_peak_ramp[-1]]
                        bandwidth_ramp = f_high_ramp - f_low_ramp
                        # 通过判断-3db峰是否碰到边界来判断数据是否valid
                        if indices_above_half_peak_ramp[0] > 5 and indices_above_half_peak_ramp[-1] < len(ramp) - 5:
                            ramp_valid = True
                    else:
                        f_low_ramp = 0
                        f_high_ramp = 0
                        bandwidth_ramp = 0  # 如果没有找到符合条件的点，返回0

                    print(f"At round {round_count}, rf of {np.format_float_positional(Rf,precision=2,unique=False)} kohm has a {np.format_float_positional(bandwidth_ramp/1e6,precision=4)} MHz bandwidth;")

                    # 更新一下进度条
                    progress.update(task, advance=1)

                    # 通过目前找到的大于目标带宽的最小带宽、小于目标带宽的最大带宽以及本次测试带宽的关系来更改下一次测试的Rf值
                    # 存在两种情况：
                    # 1. 还未找到大于或小于目标带宽的带宽，使用固定方向的搜索，步长可以调整
                    #       - 一开始因为没有上下界，所以第一次搜索一定找到一个界，而后就往另一个方向搜索，必定带宽也一个方向变化，这是由反馈电阻和带宽的确定的负相关关系决定的，如果这个负相关因为特定原因不满足，那么这里的搜索可能无效
                    #       - 固定方向搜索的时候可以有搜索快慢，如果得到的带宽结果已经很接近，就用小步长搜索上下界
                    # 2. 已经找到大于和小于目标带宽的带宽，那么通过在中间某个位置取新的Rf值，逐渐逼近
                    #       - 取值方法可以用二分法，也可以结合已知的带宽关系按照比例取Rf
                    # 3. 如果找到了足够接近的上下界，就取其中的上界对应的电阻
                    delta_Rf = Rf/2 # 固定方向搜索步长与当前Rf成比例
                    if np.abs(bandwidth_ramp -target_bandwidth) < target_bandwidth / 100: # 在一开始就足够接近目标带宽的时候让delta_Rf快速衰减
                        delta_Rf = delta_Rf / 8 
                    elif np.abs(bandwidth_ramp -target_bandwidth) < target_bandwidth / 50:
                        delta_Rf = delta_Rf / 4

                    if bandwidth_ramp >= target_bandwidth:
                        bandwidth_top = bandwidth_ramp
                        Rf_top = Rf
                        if Rf_btm == 0:# 仅找到上界，使用固定大小搜索
                            Rf = round(Rf + delta_Rf,2)
                        else:          # 已经找到上下界，使用划分法搜索
                            Rf = round(((target_bandwidth - bandwidth_btm)/(bandwidth_top-bandwidth_btm)*(Rf_top-Rf_btm)+Rf_btm)*2/3 + (Rf_top+Rf_btm)/2/3,2) # 保留两位小数，和写到spice网表中的保持一致
                    elif bandwidth_ramp < target_bandwidth:
                        bandwidth_btm = bandwidth_ramp
                        Rf_btm = Rf
                        if Rf_top == 0:# 仅找到下界，使用固定大小搜索
                            Rf = round(Rf - delta_Rf,2)
                        else:          # 已经找到上下界，使用划分法搜索
                            Rf = round(((target_bandwidth - bandwidth_btm)/(bandwidth_top-bandwidth_btm)*(Rf_top-Rf_btm)+Rf_btm)*2/3 + (Rf_top+Rf_btm)/2/3,2) # 保留两位小数，和写到spice网表中的保持一致

                    if bandwidth_top - target_bandwidth < target_bandwidth*bandwidth_precision:
                        Rf = Rf_top
                        bandwidth_ramp = bandwidth_top
                        print(f"Found optimal rf of {np.format_float_positional(Rf,precision=2,unique=False)} kohm with {np.format_float_positional(bandwidth_ramp/1e6,precision=4)} MHz bandwidth and peak gain {np.format_float_positional(peak_value_ramp/1e3,precision=4,unique=False)} kohm.")
                        progress.update(task,advance = max_Rf_search_round - round_count)
                        optimal_Rf = True
                        break

                    # 对于Rf超过上下界的情况，直接退出
                    if Rf > maximum_Rf:
                        Rf = Rf_top
                        bandwidth_ramp = bandwidth_top
                        progress.update(task,advance = max_Rf_search_round - round_count)
                        print(f"At round {round_count} found rf of {np.format_float_positional(Rf,precision=2,unique=False)} kohm with {np.format_float_positional(bandwidth_ramp/1e6,precision=4)} MHz bandwidth and peak gain {np.format_float_positional(peak_value_ramp/1e3,precision=4,unique=False)} kohm. Quit early with not optimal Rf.")
                        break
                    elif Rf <= minimum_Rf:
                        Rf = Rf_btm
                        bandwidth_ramp = bandwidth_btm
                        progress.update(task,advance = max_Rf_search_round - round_count)
                        print(f"At round {round_count} found rf of {np.format_float_positional(Rf,precision=2,unique=False)} kohm with {np.format_float_positional(bandwidth_ramp/1e6,precision=4)} MHz bandwidth and peak gain {np.format_float_positional(peak_value_ramp/1e3,precision=4,unique=False)} kohm. Quit early with not optimal Rf.")
                        break

                    # 对于计算太多轮次的就不计算了
                    if round_count >= max_Rf_search_round:
                        if Rf_top != 0:
                            Rf = Rf_top
                            bandwidth_ramp = bandwidth_top
                        print(f"At round {round_count} found rf of {np.format_float_positional(Rf,precision=2,unique=False)} kohm with {np.format_float_positional(bandwidth_ramp/1e6,precision=4)} MHz bandwidth and peak gain {np.format_float_positional(peak_value_ramp/1e3,precision=4,unique=False)} kohm. Quit early with not optimal Rf.")
                        break

                # 找到带宽最接近1MHz后存储数据
                Lf_data['peak_value_ramp_list'].append(peak_value_ramp)
                Lf_data['peak_value_rf_list'].append(Rf)
                Lf_data['optimal_Rf_list'].append(optimal_Rf)
                Lf_data['f_peak_ramp_list'].append(freq[np.argmax(ramp)])
                Lf_data['f_low_ramp_list'].append(f_low_ramp)
                Lf_data['f_high_ramp_list'].append(f_high_ramp)
                Lf_data['bandwidth_ramp_list'].append(bandwidth_ramp)
                Lf_data['ramp_valid_list'].append(ramp_valid)

                ###########################################
                # 找到最佳电阻值之后，完成以下测试：
                # 1. 噪声峰值、噪声峰值位置
                # 2. 是否自激
                # 需注意，由于ngspice本身的bug（ver44.2），
                # 在ac仿真同时进行noise仿真会导致noise仿真
                # 结果不可靠，因此此处分开仿真
                ###########################################

                # 设置用于寻找其他数据的仿真类型
                ns.clear_dot_command()
                ns.add_dot_command("tran 3n 3u") # 判断是否自激，进行tran仿真
                ns.add_dot_command("noise v(out) i1 " + dot_distribution + " " + \
                        str(sim_freq_low) + "Meg " + str(sim_freq_high) +"Meg") # 考察噪声性能，进行noise仿真

                # 重新更改元件的值
                ns.clear_mod_comp()
                # 更改反馈电感为特定模型
                ns.add_mod_comp("xl1",Lf_name)
                # 更改反馈电容的值为理论所需的电容值
                ns.add_mod_comp("c2",Cf_str)
                # 更改补偿电阻
                ns.add_mod_comp("l2",Lc_str)
                # 更改反馈电阻为二分测试最后找到的电阻值Rf
                Rf_str = np.format_float_positional(Rf,precision=2,unique=False) + 'k' # 电阻数值以kOhm为单位
                ns.add_mod_comp("r2",Rf_str)

                # 运行仿真
                arrs,plots = ns.run()

                # 取出噪声相关参数
                freq = np.real(arrs[1]['frequency'])
                out_noise_density = arrs[1]['onoise_spectrum']
                # 找到信号峰值时对应的噪声值（根据避免ngspice bug之后的仿真实验，发现噪声不具有峰值特性，而呈现谷状特性）
                Lf_data['out_noise_at_sig_peak_list'].append(out_noise_density[np.argmax(ramp)])
                    
                # 判断是否出现自激
                vout_mag_max = np.max(np.abs(np.real(arrs[0]['v(out)'])))
                # 通过tran仿真的最大vout是否大于1v来判断是否自激
                if vout_mag_max > 1:
                    Lf_data['sim_stable_list'].append(False)
                    print(f"Warning! It is not stable.")
                else:
                    Lf_data['sim_stable_list'].append(True)
                    print(f"It is stable.")

            # 将单个反馈电感对应的数据存储到data中
            data[Lf_name] = Lf_data

        # 将data保存
        with open(f"{len(Lf_dict)}Lf_change_Lc_{str(Lc_low).replace('.','u')}_{str(Lc_high).replace('.','u')}_Rf.pkl", 'wb') as f:
            pickle.dump(data, f)

def draw(file_name):
    # 读取pkl文件中的data字典
    with open(file_name, 'rb') as f:
        data = pickle.load(f)

    for Lf_name in data:
        # 获取该电感的字典数据
        Lf_data = data.get(Lf_name, None)

        # 提取所需的数据
        Lc_list = Lf_data['Lc_list']
        Cf_value = Lf_data['Cf_value']
        optimal_Cf = Lf_data['optimal_Cf']
        peak_value_ramp_list = Lf_data['peak_value_ramp_list']
        peak_value_rf_list = Lf_data['peak_value_rf_list']
        optimal_Rf_list = Lf_data['optimal_Rf_list']
        f_peak_ramp_list = Lf_data['f_peak_ramp_list']
        f_low_ramp_list = Lf_data['f_low_ramp_list']
        f_high_ramp_list = Lf_data['f_high_ramp_list']
        bandwidth_ramp_list = Lf_data['bandwidth_ramp_list']
        ramp_valid_list = Lf_data['ramp_valid_list']
        out_noise_at_sig_peak_list = Lf_data['out_noise_at_sig_peak_list']
        sim_stable_list = Lf_data['sim_stable_list']

        # 创建一个新的图形窗口
        fig, axs = plt.subplots(3, 1, figsize=(10, 12))  # 2行1列子图，调整窗口大小

        # 1. 增益峰值和对应噪声值的图
        ax1 = axs[0]
        ax1.plot(Lc_list, peak_value_ramp_list, label='Gain Peak Value', color='g', linestyle='-', marker='o')
        ax1.set_xlabel('Lc (Compensating Inductance)')
        ax1.set_ylabel('Gain Peak Value', color='g')
        ax1.tick_params(axis='y', labelcolor='g')

        # 创建第二个y轴
        ax2 = ax1.twinx()
        ax2.plot(Lc_list, out_noise_at_sig_peak_list, label='Noise Value at Gain Peak', color='r', linestyle='-', marker='o')
        ax2.set_ylabel('Noise Peak Value', color='r')
        ax2.tick_params(axis='y', labelcolor='r')

        # 设置标题和图例
        ax1.set_title(f"Gain Peak Value and Noise value for {Lf_name} with Cf of {Cf_value} pF")
        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')

        # 标记无效区域
        mark_span = (Lc_list[1]-Lc_list[0])/3
        for i in range(len(Lc_list)):
            # 判断自激与数据无效的情况
            if (not ramp_valid_list[i]) and (not sim_stable_list[i]):
                ax1.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='violet', alpha=0.2, zorder=0)  # 淡紫色，数据无效且自激
            elif not ramp_valid_list[i]:
                ax1.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='lightblue', alpha=0.2, zorder=0)  # 淡蓝色，数据无效
            elif not sim_stable_list[i]:
                ax1.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='red', alpha=0.2, zorder=0)  # 红色，自激
        # 2. 噪声峰值频率
        ax3 = axs[1]
        ax3.plot(Lc_list, f_peak_ramp_list, label='Gain Peak Frequency', color='purple', linestyle=':', marker='d')
        ax3.set_ylabel('Frequency (Hz)', color='black')
        ax3.tick_params(axis='y', labelcolor='black')

        # 标记无效区域
        for i in range(len(Lc_list)):
            # 判断自激与数据无效的情况
            if (not ramp_valid_list[i]) and (not sim_stable_list[i]):
                ax3.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='violet', alpha=0.2, zorder=0)  # 淡紫色，数据无效且自激
            elif not ramp_valid_list[i]:
                ax3.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='lightblue', alpha=0.2, zorder=0)  # 淡蓝色，数据无效
            elif not sim_stable_list[i]:
                ax3.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='red', alpha=0.2, zorder=0)  # 红色，自激

        # 设置标题和图例
        ax3.set_title(f"Gain and Noise Peak Frequency for {Lf_name} with Cf of {Cf_value} pF")
        ax3.legend(loc='upper left')

        # 3. 使用二分法逼近1MHz时对应的反馈电阻Rf、增益带宽以及搜索的Rf是否是optimal的
        ax4 = axs[2]
        ax4.plot(Lc_list, bandwidth_ramp_list, label='Gain Bandwidth (Delta F)', color='b', linestyle='-', marker='x')
        ax4.set_ylabel('Gain Bandwidth (Hz)', color='b')
        ax4.tick_params(axis='y', labelcolor='b')

        # 标记无效区域
        for i in range(len(Lc_list)):
            # 判断没有取到理想Rf的情况
            if optimal_Rf_list[i] != True:
                ax4.axvspan(Lc_list[i]-mark_span, Lc_list[i]+mark_span, color='green', alpha=0.2, zorder=0)  # 淡紫色，数据无效且自激

        # 创建第二个y轴
        ax5 = ax4.twinx()
        ax5.plot(Lc_list, peak_value_rf_list, label='Optimal Rf', color='black', linestyle='-', marker='o')
        ax5.set_xlabel('Lc (Compensating Inductance)')
        ax5.set_ylabel('Optimal Rf', color='black')
        ax5.tick_params(axis='y', labelcolor='black')

        # 设置标题和图例
        ax4.set_title(f"Gain Peak Frequency and Optimal Rf for {Lf_name} with Cf of {Cf_value} pF")
        ax4.legend(loc='upper left')
        ax5.legend(loc='upper right')

        # 展示图形
        plt.tight_layout()  # 自动调整布局，防止图表重叠
        plt.show()

# 设置命令行参数解析
def main():
    parser = argparse.ArgumentParser(description="Run different functions based on command line arguments.")
    parser.add_argument('-s', '--sim', action='store_true', help="Run the sim function")
    parser.add_argument('-d', '--draw', type=str, help="Run the draw function with a file name")

    # 解析命令行参数
    args = parser.parse_args()

    # 根据传入的参数运行对应的函数
    if args.sim:
        sim()
    elif args.draw:
        # 如果-d参数提供了文件名，传递给 draw 函数
        draw(args.draw)
    else:
        print("No valid argument provided. Use -s for sim or -d <filename> for draw.")

# 启动程序
if __name__ == "__main__":
    main()

