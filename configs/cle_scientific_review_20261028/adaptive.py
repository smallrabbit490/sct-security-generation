"""未启动的选档训练改用Joint选模；原样保留82/164题扩大条件。"""
from configs.cle_weekly_reduced_20261028 import adaptive as original
from .router import fit_model

# 只影响此独立命令进程；原脚本和活动学习、功能安全进程完全不变。
original.ga.fit_model = fit_model

if __name__ == '__main__':
    original.main()
