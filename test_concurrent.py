#!/usr/bin/env python3
"""
YOLOv5 API 并发测试脚本

使用方法:
    python test_concurrent.py --url http://localhost:8080 --api-key test-api-key-123
    python test_concurrent.py --url http://your-domain.com --api-key your-key --concurrency 50 --requests 200
    python test_concurrent.py --url http://localhost:8080 --api-key test-api-key-123 --image-dir /path/to/images
"""

import argparse
import base64
import json
import time
import statistics
import threading
import queue
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request, error
from io import BytesIO
from pathlib import Path

def load_images_from_dir(image_dir: str) -> list:
    """从文件夹加载所有图片并转为 Base64"""
    supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif'}
    images = []

    image_path = Path(image_dir)
    if not image_path.exists():
        raise FileNotFoundError(f"目录不存在: {image_dir}")

    for file in image_path.iterdir():
        if file.suffix.lower() in supported_formats:
            try:
                with open(file, 'rb') as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
                    images.append({
                        'filename': file.name,
                        'base64': image_base64,
                        'size': len(image_base64)
                    })
            except Exception as e:
                print(f"⚠️  跳过文件 {file.name}: {e}")

    if not images:
        raise ValueError(f"目录中没有找到支持的图片文件: {image_dir}")

    return images


# 生成测试图片（简单的彩色图片）
def generate_test_image(width=640, height=480):
    """生成一个简单的测试图片（不依赖 PIL）"""
    try:
        from PIL import Image
        import random

        # 创建随机颜色的图片
        img = Image.new('RGB', (width, height),
                       (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except ImportError:
        # 如果没有 PIL，使用预设的小图片
        # 这是一个 1x1 红色像素的 JPEG
        minimal_jpeg = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
            0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
            0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
            0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
            0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
            0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
            0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
            0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
            0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
            0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
            0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
            0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
            0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
            0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
            0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
            0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
            0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x45, 0x00,
            0xFF, 0xD9
        ])
        return base64.b64encode(minimal_jpeg).decode('utf-8')


class APITester:
    """API 并发测试器"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.results = queue.Queue()

    def single_request(self, image_data: dict, request_id: int) -> dict:
        """发送单个检测请求"""
        url = f"{self.base_url}/api/aapi"

        # 支持传入 dict（包含 filename）或 str（纯 base64）
        if isinstance(image_data, dict):
            image_base64 = image_data['base64']
            filename = image_data.get('filename', 'unknown')
        else:
            image_base64 = image_data
            filename = 'generated'

        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }

        data = json.dumps({'img': image_base64}).encode('utf-8')

        start_time = time.time()
        result = {
            'request_id': request_id,
            'filename': filename,
            'success': False,
            'status_code': None,
            'response_time': 0,
            'detections': 0,
            'detection_details': [],
            'error': None
        }

        try:
            req = request.Request(url, data=data, headers=headers, method='POST')
            with request.urlopen(req, timeout=self.timeout) as response:
                result['status_code'] = response.status
                response_data = json.loads(response.read().decode('utf-8'))
                result['success'] = True
                result['detections'] = len(response_data.get('detections', []))
                result['detection_details'] = response_data.get('detections', [])
                result['process_time'] = response_data.get('process_time', 0)

        except error.HTTPError as e:
            result['status_code'] = e.code
            result['error'] = f"HTTP {e.code}: {e.reason}"
        except error.URLError as e:
            result['error'] = f"URL Error: {e.reason}"
        except Exception as e:
            result['error'] = str(e)

        result['response_time'] = time.time() - start_time
        return result

    def run_concurrent_test(self, concurrency: int, total_requests: int, images: list) -> dict:
        """运行并发测试"""
        print(f"\n{'='*60}")
        print(f"开始并发测试")
        print(f"{'='*60}")
        print(f"目标地址: {self.base_url}")
        print(f"并发数: {concurrency}")
        print(f"总请求数: {total_requests}")
        print(f"图片数量: {len(images)}")
        print(f"{'='*60}\n")

        results = []
        start_time = time.time()
        completed = 0

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {}
            for i in range(total_requests):
                # 循环使用图片列表
                image_data = images[i % len(images)]
                futures[executor.submit(self.single_request, image_data, i)] = i

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1

                # 进度显示
                if completed % 10 == 0 or completed == total_requests:
                    success_count = sum(1 for r in results if r['success'])
                    print(f"进度: {completed}/{total_requests} | 成功: {success_count} | 失败: {completed - success_count}")

        total_time = time.time() - start_time

        # 统计分析
        return self.analyze_results(results, total_time, concurrency)

    def analyze_results(self, results: list, total_time: float, concurrency: int) -> dict:
        """分析测试结果"""
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        response_times = [r['response_time'] for r in successful]
        process_times = [r.get('process_time', 0) for r in successful if r.get('process_time')]

        stats = {
            'total_requests': len(results),
            'successful': len(successful),
            'failed': len(failed),
            'success_rate': len(successful) / len(results) * 100 if results else 0,
            'total_time': total_time,
            'qps': len(results) / total_time if total_time > 0 else 0,
            'concurrency': concurrency,
        }

        if response_times:
            stats['response_time'] = {
                'min': min(response_times),
                'max': max(response_times),
                'avg': statistics.mean(response_times),
                'median': statistics.median(response_times),
                'p95': sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) >= 20 else max(response_times),
                'p99': sorted(response_times)[int(len(response_times) * 0.99)] if len(response_times) >= 100 else max(response_times),
            }

        if process_times:
            stats['process_time'] = {
                'min': min(process_times),
                'max': max(process_times),
                'avg': statistics.mean(process_times),
            }

        # 错误统计
        if failed:
            error_counts = {}
            for r in failed:
                err = r.get('error', 'Unknown')
                error_counts[err] = error_counts.get(err, 0) + 1
            stats['errors'] = error_counts

        return stats

    def print_report(self, stats: dict):
        """打印测试报告"""
        print(f"\n{'='*60}")
        print("测试结果报告")
        print(f"{'='*60}")

        print(f"\n📊 基本统计:")
        print(f"   总请求数:     {stats['total_requests']}")
        print(f"   成功请求:     {stats['successful']}")
        print(f"   失败请求:     {stats['failed']}")
        print(f"   成功率:       {stats['success_rate']:.2f}%")
        print(f"   总耗时:       {stats['total_time']:.2f}s")
        print(f"   并发数:       {stats['concurrency']}")
        print(f"   QPS:          {stats['qps']:.2f}")

        if 'response_time' in stats:
            rt = stats['response_time']
            print(f"\n⏱️  响应时间 (秒):")
            print(f"   最小:         {rt['min']:.3f}s")
            print(f"   最大:         {rt['max']:.3f}s")
            print(f"   平均:         {rt['avg']:.3f}s")
            print(f"   中位数:       {rt['median']:.3f}s")
            print(f"   P95:          {rt['p95']:.3f}s")
            print(f"   P99:          {rt['p99']:.3f}s")

        if 'process_time' in stats:
            pt = stats['process_time']
            print(f"\n🔍 模型推理时间 (秒):")
            print(f"   最小:         {pt['min']:.3f}s")
            print(f"   最大:         {pt['max']:.3f}s")
            print(f"   平均:         {pt['avg']:.3f}s")

        if 'errors' in stats:
            print(f"\n❌ 错误统计:")
            for err, count in stats['errors'].items():
                print(f"   {err}: {count}")

        print(f"\n{'='*60}")

        # 性能评估
        print("\n📈 性能评估:")
        qps = stats['qps']
        if qps >= 50:
            print(f"   ✅ QPS {qps:.1f} - 性能优秀")
        elif qps >= 20:
            print(f"   ⚠️  QPS {qps:.1f} - 性能一般，建议增加 Worker 或优化模型")
        else:
            print(f"   ❌ QPS {qps:.1f} - 性能较低，建议检查服务器配置")

        if stats['success_rate'] >= 99:
            print(f"   ✅ 成功率 {stats['success_rate']:.1f}% - 稳定性优秀")
        elif stats['success_rate'] >= 95:
            print(f"   ⚠️  成功率 {stats['success_rate']:.1f}% - 存在少量失败")
        else:
            print(f"   ❌ 成功率 {stats['success_rate']:.1f}% - 需要排查问题")


def health_check(base_url: str) -> bool:
    """健康检查"""
    url = f"{base_url.rstrip('/')}/api/health"
    try:
        req = request.Request(url)
        with request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description='YOLOv5 API 并发测试工具')
    parser.add_argument('--url', type=str, default='http://localhost:8080',
                       help='API 服务地址 (默认: http://localhost:8080)')
    parser.add_argument('--api-key', type=str, default='test-api-key-123',
                       help='API Key (默认: test-api-key-123)')
    parser.add_argument('--concurrency', '-c', type=int, default=10,
                       help='并发数 (默认: 10)')
    parser.add_argument('--requests', '-n', type=int, default=100,
                       help='总请求数 (默认: 100)')
    parser.add_argument('--timeout', '-t', type=int, default=30,
                       help='请求超时时间(秒) (默认: 30)')
    parser.add_argument('--image', type=str, default=None,
                       help='测试图片路径 (可选，默认使用生成的测试图片)')
    parser.add_argument('--image-dir', type=str, default=None,
                       help='测试图片文件夹路径 (可选，会使用文件夹中所有图片)')

    args = parser.parse_args()

    print("🚀 YOLOv5 API 并发测试工具")
    print(f"{'='*60}")

    # 健康检查
    print(f"检查服务状态: {args.url}")
    if not health_check(args.url):
        print("❌ 服务不可用，请检查服务是否启动")
        return 1
    print("✅ 服务正常\n")

    # 准备测试图片
    images = []

    if args.image_dir:
        # 从文件夹加载图片
        print(f"📁 从文件夹加载图片: {args.image_dir}")
        images = load_images_from_dir(args.image_dir)
        print(f"   找到 {len(images)} 张图片:")
        for img in images[:5]:  # 只显示前5张
            print(f"   - {img['filename']} ({img['size']} bytes)")
        if len(images) > 5:
            print(f"   ... 还有 {len(images) - 5} 张图片")
    elif args.image:
        # 加载单张图片
        print(f"加载测试图片: {args.image}")
        with open(args.image, 'rb') as f:
            image_base64 = base64.b64encode(f.read()).decode('utf-8')
        images = [{'filename': os.path.basename(args.image), 'base64': image_base64, 'size': len(image_base64)}]
    else:
        # 生成测试图片
        print("生成测试图片...")
        image_base64 = generate_test_image()
        images = [{'filename': 'generated.jpg', 'base64': image_base64, 'size': len(image_base64)}]

    print(f"\n总图片数: {len(images)}")
    total_size = sum(img['size'] for img in images)
    print(f"总大小: {total_size / 1024:.1f} KB (Base64)\n")

    # 运行测试
    tester = APITester(args.url, args.api_key, args.timeout)
    stats = tester.run_concurrent_test(args.concurrency, args.requests, images)

    # 打印报告
    tester.print_report(stats)

    return 0 if stats['success_rate'] >= 95 else 1


if __name__ == '__main__':
    exit(main())
