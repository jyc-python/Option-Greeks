def GetOptionData(us_code, date):
#     date = "2020-04-03" # 报表日期
#     us_code = "000300.SH" #期权标的
    # 导出数据的字段，基本不用调整吧
    field = "us_code,option_code,option_name,strike_price,month,call_put,expiredate,multiplier" 
    # 翻译一下：标的代码，期权代码，期权名称，行权价，期权交割月份，期权类型，剩余存续期（天），合约乘数
    wind_data = w.wset("optionchain","date="+date+";us_code="+us_code+";option_var=全部;call_put=全部;field="+field)
    if wind_data.ErrorCode != 0:
        print("WIND数据读取有误，ErrorCode="+data.ErrorCode)
        sys.exit()
    data = pd.DataFrame(wind_data.Data,index = wind_data.Fields).T
    c_p = []
    for i in data["call_put"]:
        temp = "C" if i =="认购" else "P"
        c_p.append(temp)
    data["call_put"] = c_p 
    
    # 取data中的期权代码，用w.wsd取结算价
    input = ",".join(data["option_code"])
    wind_settle=w.wsd(input, "settle", date, date, "")
    if wind_settle.ErrorCode != 0:
        print("WIND数据读取有误，ErrorCode="+wind_settle.ErrorCode)
        sys.exit()
    data["settlement_price"]=wind_settle.Data[0]
    return data

# 无风险利率使用SHIBOR6M
def GetRiskFreeRate(date):
    r = w.wsd("SHIBOR6M.IR", "close,settle", date, date, "")
    if r.ErrorCode !=0:
        print("WIND数据读取有误，ErrorCode="+r.ErrorCode)
        sys.exit()
    r = r.Data[0][0]/100
    return r

# 找到K0从而算出隐含远期及相应贴现F
def GetF(us_code, date):
    # 需要引用func GetRiskFreeRate, GetOptionData
    data = GetOptionData(us_code, date)
    # Ci_Pi 的意思是对call取正数结算价，对put取负数结算价
    # CiPi是（Ci-Pi）
    # CiPi_abs是取了绝对值用来求最小
    data = data[["month","option_code","us_code","option_name","call_put",
                 "settlement_price","strike_price","expiredate","multiplier"]]
    data["Ci_Pi"]=""
    # call的结算价用+，put结算价用-
    # 需注意的是，data["CiPi"]并不是实际的CiPi(后面我会drop掉的)
    f1 = lambda data,call_put,P:data[P] if data[call_put] == "C" else -data[P]
    data["Ci_Pi"]=data.apply(f1,axis=1,args=("call_put","settlement_price"))

    # CiPi是一个用来计算的过程数据集
    CiPi = data.groupby(by = ["month","strike_price","expiredate"])["Ci_Pi"].sum()   
    CiPi = CiPi.reset_index()
    CiPi.rename(columns={'Ci_Pi':'CiPi'}, inplace = True)
        
    CiPi["CiPi_abs"] = ""
    CiPi["CiPi_abs"] = abs(CiPi["CiPi"])

    # C0P0_abs可以用来通过布尔索引取得0字段数据
    C0P0_abs = CiPi.groupby(by=["month"])["CiPi_abs"].min()
    C0P0_abs = pd.DataFrame(C0P0_abs)
    C0P0_abs.rename(columns={'CiPi_abs':'C0P0_abs'}, inplace = True)
    C0P0_dic={}
    K0_dic={}
    # 输出的是{month：具体数值}，然后合并去data去哦
    for i in C0P0_abs.index:
        for j in CiPi.index.values:
            if (CiPi.loc[j,"month"]== i) & (CiPi.loc[j,"CiPi_abs"] == C0P0_abs.loc[i,"C0P0_abs"]):
                C0P0_dic.update({i:CiPi.loc[j,"CiPi"]})
                K0_dic.update({i:CiPi.loc[j,"strike_price"]})

    data = data.drop("Ci_Pi",axis = 1)

    data["C0P0"]=""
    data["K0"]=""
    for i in data.index.values:
        data.loc[i,"C0P0"] = C0P0_dic[data.loc[i,"month"]]
        data.loc[i,"K0"] = K0_dic[data.loc[i,"month"]]

    # 此时数据集data已经包含了C0P0 K0,可以结合expiredate,r求隐含远期价格Futures*
    # 注意用strike price不行哦，用的是K0
    r = GetRiskFreeRate(date)
    data["Futures*"]=""
    data["F"]=""  # 隐含远期价格贴现，用于计算iv
    for i in data.index.values:
        data.loc[i,"Futures*"] = data.loc[i,"C0P0"]*np.e**(r*data.loc[i,"expiredate"]/365)+data.loc[i,"K0"]
        data.loc[i,"F"] = data.loc[i,"Futures*"]*np.e**(-r*data.loc[i,"expiredate"]/365)
    return data

# 根据上面的参数，计算咱们的greeks们
def GetGreeks(us_code, date):  
# date = "2020-04-02"
# us_code = "510050.SH"
    r = GetRiskFreeRate(date)
    data = GetF(us_code, date)
    underlying_settlement = w.wsd(us_code, "close", date, date, "")
    if underlying_settlement.ErrorCode != 0:
        print("WIND数据读取有误，ErrorCode="+underlying_settlement.ErrorCode)
        sys.exit()
    underlying_settlement = underlying_settlement.Data[0][0]
    data = pd.concat((data, pd.DataFrame(columns=["iv0","iv","delta","gamma","vega","theta","rho"])),axis = 1)

    for i in data.index.values:
        OptionType = data.call_put[i]
        S = data.loc[i,"F"]
        X = data.loc[i,"strike_price"]
        T = data.loc[i,"expiredate"]/365
        R = r
        d = 0
        Target = data.loc[i,"settlement_price"]
        data.loc[i,"iv0"] = iv(OptionType, S, X, T, R, d, Target)

    # iv0是对于隐含远期贴现计算出的隐含波动率
    # 有了以后要给一下iv用于计算其他greeks
    c_dic = {}
    p_dic = {}
    for i in data.index.values:
        if data.loc[i,"call_put"]=="C":
            c_dic.update({str(data.loc[i,"month"])+str(data.loc[i,"strike_price"]):data.loc[i,"iv0"]})
        else:
            p_dic.update({str(data.loc[i,"month"])+str(data.loc[i,"strike_price"]):data.loc[i,"iv0"]})

    for i in data.index.values:
        OptionType = data.loc[i,"call_put"]
        S = data.loc[i,"F"]
        X = data.loc[i,"strike_price"]
        T = data.loc[i,"expiredate"]/365
        R = r
        d = 0
        if X > S:
            v = c_dic[str(data.loc[i,"month"])+str(data.loc[i,"strike_price"])]
        else:
            v = p_dic[str(data.loc[i,"month"])+str(data.loc[i,"strike_price"])]
        data.loc[i,"iv"] = v
        data.loc[i,"delta"] = OptionDelta(OptionType, S, X, T, R, v, d)

        #前人的模板上，这里的S就不用隐含的F贴现了，于是我就继续这么算（这样和别人可以对上）
        data.loc[i,"gamma"] = OptionGamma(OptionType, underlying_settlement, X, T, R, v, d)
        data.loc[i,"vega"]= OptionVega(OptionType, underlying_settlement, X, T, R, v, d)
        data.loc[i,"theta"] = OptionTheta(OptionType, underlying_settlement, X, T, R, v, d)
        data.loc[i,"rho"] = OptionRho(OptionType, underlying_settlement, X, T, R, v, d)
    return data
