#!/bin/bash
# 清理 7 天前的问题图片
# 用法: ./scripts/cleanup_old_images.sh
# 建议添加到 crontab: 0 3 * * * /path/to/cleanup_old_images.sh

PROBLEM_IMAGES_DIR="${1:-/app/problem_images}"
DAYS_TO_KEEP="${2:-7}"

echo "Cleaning images older than ${DAYS_TO_KEEP} days in ${PROBLEM_IMAGES_DIR}"

# 删除超过指定天数的文件
find "${PROBLEM_IMAGES_DIR}" -type f \( -name "*.jpg" -o -name "*.txt" \) -mtime +${DAYS_TO_KEEP} -delete

# 删除空目录
find "${PROBLEM_IMAGES_DIR}" -type d -empty -delete

echo "Cleanup completed at $(date)"
