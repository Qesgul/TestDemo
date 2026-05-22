"""
GrowingIO Protobuf 埋点解码工具
用法：
  python gio_decoder.py                        # 交互式输入 hex 字符串
  python gio_decoder.py "0a 1b 08 01 ..."      # 命令行传入 hex 字符串
  python gio_decoder.py --file request.bin     # 读取二进制文件
"""

import sys
import json
import re
import struct


# ──────────────────────────────────────────────
# 纯 Python 实现的 protobuf raw decoder
# 无需安装任何第三方库
# ──────────────────────────────────────────────

WIRE_VARINT = 0
WIRE_64BIT  = 1
WIRE_LENGTH = 2
WIRE_32BIT  = 5


def read_varint(data: bytes, pos: int):
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            break
    return result, pos


def decode_raw(data: bytes, depth: int = 0) -> dict:
    """递归解析 protobuf 二进制，不需要 .proto schema"""
    result = {}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = read_varint(data, pos)
        except Exception:
            break

        field_number = tag_wire >> 3
        wire_type    = tag_wire & 0x07

        if field_number == 0:
            break

        key = str(field_number)

        try:
            if wire_type == WIRE_VARINT:
                value, pos = read_varint(data, pos)

            elif wire_type == WIRE_64BIT:
                if pos + 8 > len(data):
                    break
                raw = data[pos:pos+8]
                pos += 8
                value = struct.unpack('<Q', raw)[0]

            elif wire_type == WIRE_LENGTH:
                length, pos = read_varint(data, pos)
                if pos + length > len(data):
                    break
                chunk = data[pos:pos+length]
                pos += length

                # 优先尝试 UTF-8 字符串
                try:
                    value = chunk.decode('utf-8')
                except UnicodeDecodeError:
                    # 尝试递归解析为嵌套 message
                    try:
                        nested = decode_raw(chunk, depth + 1)
                        if nested:
                            value = nested
                        else:
                            value = chunk.hex()
                    except Exception:
                        value = chunk.hex()

            elif wire_type == WIRE_32BIT:
                if pos + 4 > len(data):
                    break
                raw = data[pos:pos+4]
                pos += 4
                value = struct.unpack('<I', raw)[0]

            else:
                # 未知 wire type，跳过剩余
                break

        except Exception:
            break

        # 同一字段多次出现 → 转成列表
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value

    return result


# ──────────────────────────────────────────────
# 输入处理
# ──────────────────────────────────────────────

def normalize_hex(raw: str) -> bytes:
    """
    兼容多种 hex 格式：
      "0a 1b 08"  带空格
      "0a1b08"    紧凑
      "0A:1B:08"  冒号分隔
    """
    cleaned = re.sub(r'[^0-9a-fA-F]', '', raw)
    if len(cleaned) % 2 != 0:
        raise ValueError(f"十六进制字符串长度为奇数（{len(cleaned)} 个字符），请检查输入")
    return bytes.fromhex(cleaned)


def load_input() -> bytes:
    # 1. 命令行 --file
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        path = sys.argv[idx + 1]
        with open(path, 'rb') as f:
            return f.read()

    # 2. 命令行直接传 hex 字符串
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        return normalize_hex(sys.argv[1])

    # 3. 交互式输入
    print("请粘贴 Fiddler Hex 内容（支持带空格/冒号格式），输入完成后按两次 Enter：")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == '' and lines and lines[-1] == '':
            break
        lines.append(line)
    raw_hex = ' '.join(lines)
    return normalize_hex(raw_hex)


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    try:
        data = load_input()
    except (IndexError, FileNotFoundError, ValueError) as e:
        print(f"[错误] 输入读取失败: {e}")
        sys.exit(1)

    print(f"\n[INFO] 数据长度: {len(data)} 字节\n")

    result = decode_raw(data)

    if not result:
        print("[警告] 解析结果为空，可能数据已压缩（gzip/zlib）或格式不是标准 protobuf")
        print("原始 hex:", data.hex())
        return

    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)


if __name__ == '__main__':
    main()
