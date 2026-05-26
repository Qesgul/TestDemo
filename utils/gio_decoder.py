"""
GrowingIO 埋点请求解码工具
编码格式：LZString.compress() 原始字节（非标准压缩，非 protobuf）

用法：
  python gio_decoder.py                        # 交互式粘贴 Fiddler 文本内容
  python gio_decoder.py --file request.bin     # 读取从 Fiddler 保存的二进制文件
  python gio_decoder.py "0a 1b 08 01 ..."      # 命令行传入 hex 字符串（备用）

依赖：pip install lzstring
"""

import sys
import json
import re
import struct
import gzip
import zlib
import base64


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
# LZString 解码（GrowingIO 实际使用的格式）
# ──────────────────────────────────────────────

def decode_lzstring(data: bytes):
    """
    GrowingIO JS SDK 使用 LZString.compress() 压缩后直接发送原始字节。
    Python 解码方法：先 base64 包装，再用 decompressFromBase64 还原。
    返回解压后的字符串，失败返回 None。
    """
    try:
        from lzstring import LZString
        b64 = base64.b64encode(data).decode('ascii')
        result = LZString().decompressFromBase64(b64)
        if result and len(result) > 2:
            return result
    except ImportError:
        raise RuntimeError("缺少依赖，请执行: pip install lzstring")
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# 兜底：标准压缩格式检测
# ──────────────────────────────────────────────

def detect_and_decompress(data: bytes) -> tuple:
    """
    自动检测压缩格式并解压，返回 (解压后数据, 压缩格式描述)
    支持: gzip, zlib(deflate), 原始数据
    """
    # gzip 魔数: 1f 8b
    if data[:2] == b'\x1f\x8b':
        try:
            decompressed = gzip.decompress(data)
            return decompressed, 'gzip'
        except Exception as e:
            return data, f'gzip魔数匹配但解压失败: {e}'

    # zlib 魔数: 78 01 / 78 9c / 78 da / 78 5e
    if data[:1] == b'\x78' and data[1:2] in (b'\x01', b'\x9c', b'\xda', b'\x5e'):
        try:
            decompressed = zlib.decompress(data)
            return decompressed, 'zlib'
        except Exception as e:
            return data, f'zlib魔数匹配但解压失败: {e}'

    # 尝试 raw deflate（无 zlib header，部分 SDK 使用）
    try:
        decompressed = zlib.decompress(data, -15)
        return decompressed, 'raw deflate'
    except Exception:
        pass

    return data, '未压缩'


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


def is_hex_string(s: str) -> bool:
    """判断字符串是否为纯十六进制内容（允许空格/冒号分隔）"""
    cleaned = re.sub(r'[\s:]', '', s)
    return bool(cleaned) and all(c in '0123456789abcdefABCDEF' for c in cleaned)


def text_to_bytes(text: str) -> bytes:
    """
    将 Fiddler 文本视图复制出的乱码还原为原始字节。
    Fiddler 内部用 Latin-1 (ISO-8859-1) 渲染二进制，
    直接用 latin-1 编码即可还原。
    Windows 系统剪贴板可能用 cp1252，两者差异极小，都尝试。
    """
    for enc in ('latin-1', 'cp1252'):
        try:
            return text.encode(enc)
        except Exception:
            continue
    raise ValueError("无法将文本还原为字节，请改用 --file 模式")


def load_input() -> bytes:
    # 1. 命令行 --file
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        path = sys.argv[idx + 1]
        with open(path, 'rb') as f:
            return f.read()

    # 2. 命令行直接传 hex 字符串
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        raw = sys.argv[1]
        if is_hex_string(raw):
            return normalize_hex(raw)
        else:
            print("[INFO] 命令行参数不是纯 hex，尝试按 Latin-1 文本还原...")
            return text_to_bytes(raw)

    # 3. 交互式输入
    print("请直接粘贴 Fiddler 复制的内容（乱码文本 或 hex 均可），输入完成后按两次 Enter：")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == '' and lines and lines[-1] == '':
            break
        lines.append(line)

    raw_text = '\n'.join(lines).strip()

    if not raw_text:
        raise ValueError("未输入任何内容")

    if is_hex_string(raw_text):
        print("[INFO] 识别为 hex 字符串，直接解析...")
        return normalize_hex(raw_text)
    else:
        print("[INFO] 识别为 Fiddler 文本视图内容，按 Latin-1 还原字节...")
        return text_to_bytes(raw_text)


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    try:
        data = load_input()
    except (IndexError, FileNotFoundError, ValueError) as e:
        print(f"[错误] 输入读取失败: {e}")
        sys.exit(1)

    print(f"[INFO] 原始数据长度: {len(data)} 字节")
    print(f"[INFO] 原始头部 hex: {data[:16].hex()}")
    print()

    # ── 第一优先：LZString（GrowingIO 实际格式）──
    try:
        text = decode_lzstring(data)
        if text:
            print("[INFO] 解码成功：LZString 格式（GrowingIO 标准编码）")
            print()
            try:
                result = json.loads(text)
                events = result if isinstance(result, list) else [result]
                print(f"共 {len(events)} 条事件")
                print("=" * 60)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("=" * 60)
            except json.JSONDecodeError:
                print("[INFO] 解压内容不是 JSON，原始文本：")
                print(text[:2000])
            return
    except RuntimeError as e:
        print(f"[警告] {e}")

    # ── 第二优先：标准压缩格式 ──
    decompressed, fmt = detect_and_decompress(data)
    if fmt != '未压缩':
        print(f"[INFO] 检测到压缩格式: {fmt}，解压后长度: {len(decompressed)} 字节")
    else:
        print(f"[INFO] 未检测到压缩，尝试 protobuf 解析")
    print()

    result = decode_raw(decompressed)

    if not result:
        print("[警告] 所有解析方式均失败")
        print()
        print("── 诊断信息 ──")
        print(f"  解压格式    : {fmt}")
        print(f"  解压后 hex  : {decompressed[:64].hex()}")
        try:
            print(f"  尝试 UTF-8  : {decompressed[:200].decode('utf-8', errors='replace')}")
        except Exception:
            pass
        return

    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)


if __name__ == '__main__':
    main()
