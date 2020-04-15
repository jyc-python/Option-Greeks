from WindPy import w
import pandas as pd
import numpy as np
from scipy.stats import norm
w.start()

def dOne(S, X, T, R, v, d):
    return (np.log(S / X) + (R - d + 0.5 * v ** 2) * T) / (v * (np.sqrt(T)))
 
def NdOne(S, X, T, R, v, d):
    return np.e**(-(dOne(S, X, T, R, v, d) ** 2) / 2) / (np.sqrt(2 * np.pi))
 
def dTwo(S, X, T, R, v, d):
    return dOne(S, X, T, R, v, d) - v * np.sqrt(T)

def NdTwo(S, X, T, R, v, d):
    return norm.cdf(dTwo(S, X, T, R, v, d))

def OptionMargin(OptionType, S, X, OP):   
    if OptionType == "C":
        OptionMargin = (OP + max(0.12 * S - max(0, X - S), 0.07 * S))
    elif OptionType == "P":
        OptionMargin = (min(OP + max(0.12 * S - max(0, S - X), 0.07 * X), X))
    return OptionMargin

def OptionPrice(OptionType, S, X, T, R, v, d):
    if OptionType == "C":
        OptionPrice = np.e**(-d * T) * S * norm.cdf(dOne(S, X, T, R, v, d)) - (X * np.e**(-R * T) * norm.cdf(dTwo(S, X, T, R, v, d)))
    elif OptionType == "P":
        OptionPrice = X * np.e**(-R * T) * norm.cdf(-dTwo(S, X, T, R, v, d)) - (np.e**(-d * T) * S * norm.cdf(-dOne(S, X, T, R, v, d)))
    return OptionPrice
    
def OptionDelta(OptionType, S, X, T, R, v, d):

    if OptionType == "C":
        OptionDelta = norm.cdf(dOne(S, X, T, R, v, d))
    elif OptionType == "P":
        OptionDelta = norm.cdf(dOne(S, X, T, R, v, d)) - 1
    return OptionDelta
 
def OptionTheta(OptionType, S, X, T, R, v, d):
    if OptionType == "C":
        OptionTheta = -(S * v * NdOne(S, X, T, R, v, d)) / (2 * np.sqrt(T)) - R * X * np.e**(-R * (T)) * norm.cdf(dTwo(S, X, T, R, v, d))
    elif OptionType == "P":
        OptionTheta = -(S * v * NdOne(S, X, T, R, v, d)) / (2 * np.sqrt(T)) + R * X * np.e**(-R * (T)) * (1 - norm.cdf(dTwo(S, X, T, R, v, d)))
    return OptionTheta
 
def OptionGamma(OptionType, S, X, T, R, v, d):
#     if OptionType == "C" Or OptionType = "P":
    return NdOne(S, X, T, R, v, d) / (S * (v * np.sqrt(T)))
 
def OptionVega(OptionType, S, X, T, R, v, d):
#     If (OptionType == "C" | OptionType = "P"):
    return S * np.sqrt(T) * NdOne(S, X, T, R, v, d)
 
def OptionRho(OptionType, S, X, T, R, v, d):
    if OptionType == "C":
        OptionRho = X * T * np.e**(-R * T) * norm.cdf(dTwo(S, X, T, R, v, d))
    elif OptionType == "P":
        OptionRho = -1 * X * T * np.e**(-R * T) * (1 - norm.cdf(dTwo(S, X, T, R, v, d)))
    return OptionRho

def iv(OptionType, S, X, T, R, d, Target):
    high = 1
    low = 0.0001

    while (high - low) > 0.000001:
        if OptionPrice(OptionType, S, X, T, R, (high + low) / 2, d) > Target:
            high = (high + low) / 2
        else:
            low = (high + low) / 2
    iv = (high + low) / 2
    return iv
