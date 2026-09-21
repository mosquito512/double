#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小学四则运算题目生成与判题程序
Usage:
  生成题目: python main.py -n <count> -r <range>
  判题:     python main.py -e <exercisefile> -a <answerfile>
"""

import argparse
import random
import re
import sys
from fractions import Fraction as PyFraction


# ============================================================
# 1. 分数工具：统一用 Python 内置 Fraction 做精确运算
# ============================================================

def frac_to_str(f: PyFraction) -> str:
    """将 Fraction 转换为题目要求的字符串格式"""
    if f.denominator == 1:
        return str(f.numerator)
    # 假分数 → 带分数 a'b/c
    if abs(f.numerator) > f.denominator:
        integer_part = f.numerator // f.denominator
        remainder = f.numerator % f.denominator
        if remainder == 0:
            return str(integer_part)
        return f"{integer_part}'{remainder}/{f.denominator}"
    # 真分数 a/b
    return f"{f.numerator}/{f.denominator}"


def str_to_frac(s: str) -> PyFraction:
    """将题目中的数字字符串解析为 Fraction
    支持: '5', '3/5', '2\'3/8'
    """
    s = s.strip()
    if "'" in s:
        parts = s.split("'", 1)
        int_part = int(parts[0])
        num, den = parts[1].split("/")
        return PyFraction(int_part * int(den) + int(num), int(den))
    if "/" in s:
        num, den = s.split("/")
        return PyFraction(int(num), int(den))
    return PyFraction(int(s))


# ============================================================
# 2. 表达式 AST
# ============================================================

class Number:
    """数字叶子节点"""
    def __init__(self, value: PyFraction):
        self.value = value

    def evaluate(self) -> PyFraction:
        return self.value

    def normalize(self) -> str:
        """规范化表示（用于去重）"""
        return frac_to_str(self.value)

    def __str__(self) -> str:
        return frac_to_str(self.value)


class BinOp:
    """二元运算节点"""

    # 运算符优先级
    _PRECEDENCE = {'+': 1, '-': 1, '×': 2, '÷': 2}

    def __init__(self, op: str, left, right):
        self.op = op
        self.left = left
        self.right = right

    def evaluate(self) -> PyFraction:
        lv = self.left.evaluate()
        rv = self.right.evaluate()
        if self.op == '+':
            return lv + rv
        elif self.op == '-':
            return lv - rv
        elif self.op == '×':
            return lv * rv
        elif self.op == '÷':
            return lv / rv
        raise ValueError(f"未知运算符: {self.op}")

    def normalize(self) -> str:
        """规范化表示：+ 和 × 可交换，左右子树排序后拼接"""
        lstr = self.left.normalize()
        rstr = self.right.normalize()
        if self.op in ('+', '×'):
            lstr, rstr = sorted([lstr, rstr])
        return f"({lstr}{self.op}{rstr})"

    def _child_str(self, child, is_left: bool) -> str:
        """生成子节点字符串，必要时加括号"""
        if isinstance(child, Number):
            return str(child)
        child_prec = self._PRECEDENCE[child.op]
        parent_prec = self._PRECEDENCE[self.op]

        if child_prec < parent_prec:
            # 子表达式优先级更低，必须加括号
            return f"({child})"
        elif child_prec == parent_prec:
            if is_left:
                # 左结合：左子节点同优先级不加括号
                return str(child)
            else:
                # 右子节点：+ 和 × 可结合不加括号；- 和 ÷ 不可结合需加括号
                if self.op in ('-', '÷'):
                    return f"({child})"
                return str(child)
        else:
            # 子表达式优先级更高，不加括号
            return str(child)

    def __str__(self) -> str:
        left_str = self._child_str(self.left, is_left=True)
        right_str = self._child_str(self.right, is_left=False)
        return f"{left_str} {self.op} {right_str}"


# ============================================================
# 3. 表达式生成器
# ============================================================

def gen_number(r: int) -> Number:
    """生成一个自然数或真分数，范围受 r 控制"""
    if random.random() < 0.5 or r <= 2:
        # 自然数: 0 ~ r-1
        return Number(PyFraction(random.randint(0, r - 1)))
    else:
        # 真分数: 分母 2 ~ r-1, 分子 1 ~ 分母-1
        den = random.randint(2, r - 1)
        num = random.randint(1, den - 1)
        return Number(PyFraction(num, den))


def gen_expression(r: int, max_ops: int):
    """递归生成表达式，max_ops 为本节点及子树最多允许的运算符数量"""
    if max_ops <= 0:
        return gen_number(r)

    # 以一定概率提前终止，不生成更多运算符
    if random.random() < 0.25:
        return gen_number(r)

    op = random.choice(['+', '-', '×', '÷'])

    remaining = max_ops - 1
    left_ops = random.randint(0, remaining)
    right_ops = remaining - left_ops

    for _ in range(200):
        left = gen_expression(r, left_ops)
        right = gen_expression(r, right_ops)
        lv = left.evaluate()
        rv = right.evaluate()

        valid = True
        if op == '-':
            # 减法：左 >= 右，不产生负数
            if lv < rv:
                left, right = right, left
        elif op == '+':
            # 加法约束：左右都是真分数(<1)时，和也必须 <1
            if lv < 1 and rv < 1 and lv + rv >= 1:
                valid = False
        elif op == '÷':
            # 除法：除数不能为0
            if rv == 0:
                valid = False

        if valid:
            return BinOp(op, left, right)

    # 重试失败，返回简单数字
    return gen_number(r)


def count_ops(node) -> int:
    """统计表达式中的运算符数量"""
    if isinstance(node, Number):
        return 0
    return 1 + count_ops(node.left) + count_ops(node.right)


def generate_problem(r: int):
    """生成一道题目，返回 (表达式字符串, 答案字符串, 规范化去重键)"""
    for _ in range(2000):
        ops = random.randint(1, 3)  # 运算符个数 1~3
        expr = gen_expression(r, ops)
        # 必须至少有一个运算符（不能是纯数字）
        if isinstance(expr, Number):
            continue
        if count_ops(expr) > 3:
            continue
        result = expr.evaluate()
        if result < 0:
            continue
        expr_str = str(expr) + " ="
        answer_str = frac_to_str(result)
        norm_key = expr.normalize()
        return expr_str, answer_str, norm_key
    return None, None, None


# ============================================================
# 4. 生成模式：-n <count> -r <range>
# ============================================================

def run_generate(n: int, r: int):
    if r < 1:
        print("错误：-r 参数必须为正整数", file=sys.stderr)
        sys.exit(1)
    if n < 1:
        print("错误：-n 参数必须为正整数", file=sys.stderr)
        sys.exit(1)

    seen = set()
    exercises = []
    answers = []
    attempts = 0
    max_attempts = n * 500

    while len(exercises) < n and attempts < max_attempts:
        attempts += 1
        expr_str, answer_str, norm_key = generate_problem(r)
        if expr_str is None:
            continue
        if norm_key in seen:
            continue
        seen.add(norm_key)
        exercises.append(expr_str)
        answers.append(answer_str)

    if len(exercises) < n:
        print(f"警告：仅生成 {len(exercises)} 道不重复题目（请求 {n} 道）", file=sys.stderr)

    with open("Exercises.txt", "w", encoding="utf-8") as f:
        for i, line in enumerate(exercises, 1):
            f.write(f"{i}. {line}\n")

    with open("Answers.txt", "w", encoding="utf-8") as f:
        for i, ans in enumerate(answers, 1):
            f.write(f"{i}. {ans}\n")

    print(f"成功生成 {len(exercises)} 道题目")
    print(f"题目已保存到 Exercises.txt")
    print(f"答案已保存到 Answers.txt")


# ============================================================
# 5. 判题模式：-e <exercise_file> -a <answer_file>
# ============================================================

def parse_problem_file(filepath: str):
    """读取题目或答案文件，返回 {编号: 内容字符串}"""
    result = {}
    with open(filepath, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            dot_idx = line.index(".")
            num = int(line[:dot_idx].strip())
            content = line[dot_idx + 1:].strip()
            result[num] = content
    return result


def evaluate_expression(expr_str: str) -> PyFraction:
    """
    对题目中的表达式字符串求值（支持 + - × ÷ 和括号）。
    将表达式转换为 Fraction 运算后用 eval 计算。
    """
    s = expr_str.replace("×", "*").replace("÷", "/")
    # 带分数 2'3/8 → (2+3/8)
    s = re.sub(r"(\d+)'(\d+)/(\d+)", r"(\1+\2/\3)", s)
    # 纯分数 3/5 → (Fraction(3,5))，避免浮点误差
    s = re.sub(r"(\d+)/(\d+)", r"Fraction(\1,\2)", s)
    # 自然数保持不变

    try:
        result = eval(s, {"__builtins__": {}}, {"Fraction": PyFraction})
        if isinstance(result, PyFraction):
            return result
        # 纯自然数表达式 eval 返回 float，用 limit_denominator 消除浮点误差
        return PyFraction(result).limit_denominator(10000)
    except Exception as e:
        raise ValueError(f"表达式解析失败: {expr_str} -> {s} ({e})")


def run_grade(exercise_file: str, answer_file: str):
    problems = parse_problem_file(exercise_file)
    student_answers = parse_problem_file(answer_file)

    correct_list = []
    wrong_list = []

    for num in sorted(problems.keys()):
        expr = problems[num]
        # 去掉结尾的 "="
        expr_clean = expr.rstrip("=").strip()
        try:
            expected = evaluate_expression(expr_clean)
        except Exception:
            wrong_list.append(num)
            continue

        student_ans_str = student_answers.get(num, "")
        try:
            student_frac = str_to_frac(student_ans_str)
            if student_frac == expected:
                correct_list.append(num)
            else:
                wrong_list.append(num)
        except Exception:
            wrong_list.append(num)

    with open("Grade.txt", "w", encoding="utf-8") as f:
        f.write(f"Correct: {len(correct_list)} ({', '.join(map(str, correct_list))})\n")
        f.write(f"Wrong: {len(wrong_list)} ({', '.join(map(str, wrong_list))})\n")

    print(f"判题完成！正确: {len(correct_list)}, 错误: {len(wrong_list)}")
    print(f"结果已保存到 Grade.txt")


# ============================================================
# 6. 命令行入口
# ============================================================

def print_help():
    print("用法:")
    print("  生成题目: python main.py -n <题目个数> -r <数值范围>")
    print("  判题:     python main.py -e <题目文件> -a <答案文件>")
    print()
    print("参数说明:")
    print("  -n  生成题目的个数")
    print("  -r  数值范围（自然数、真分数分母的上界），必须为正整数")
    print("  -e  题目文件路径（判题模式）")
    print("  -a  答案文件路径（判题模式）")


def main():
    parser = argparse.ArgumentParser(description="小学四则运算题目生成程序", add_help=False)
    parser.add_argument("-n", type=int, help="生成题目的个数")
    parser.add_argument("-r", type=int, help="数值范围（必须给定）")
    parser.add_argument("-e", type=str, help="题目文件路径（判题模式）")
    parser.add_argument("-a", type=str, help="答案文件路径（判题模式）")

    args = parser.parse_args()

    # 判题模式
    if args.e and args.a:
        run_grade(args.e, args.a)
        return

    # 生成模式
    if args.n is not None and args.r is not None:
        run_generate(args.n, args.r)
        return

    # 参数不完整
    print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
