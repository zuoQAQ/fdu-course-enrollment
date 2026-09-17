"""
复旦大学研究生抢课程序
多线程并发 + csrfToken预获取 + 自动重试
"""
import requests
import threading
import time
import datetime
import re
import json
import os

cnt = 0
cnt_lock = threading.Lock()

# 缓存的csrfToken，预获取后所有线程共用
cached_token = None
cached_token_lock = threading.Lock()

# ==================== 配置区（按需修改）====================

# Cookie：优先从环境变量 QIANGKE_COOKIE 读取，其次从这里读，都没有则交互输入
QIANGKE_COOKIE = ""

# 课程信息：每组 [分类名, 课程ID1, 课程ID2, ...]，同组内按优先级排序
# 示例：抢两门政治理论课 + 一门公共选修课
classification_and_course_ids = [
    ["政治理论课", "2026202701GEIP40015.07", "2026202701GEIP40017.04"],
    ["公共选修课", "2026202701GEEC10294.01", "2026202701GEEC10296.01"]
]

# 抢课时间
START_HOUR = 12
START_MINUTE = 59
START_SECOND = 55

# 结束时间
END_HOUR = 13
END_MINUTE = 1
END_SECOND = 57

# 请求域名
target = "yjsxk.fudan.edu.cn"

# 课程类别映射
course_classification_dict = {
    "学位基础课": 8, "专业选修课": 8, "学位专业课": 8,
    "公共选修课": 9, "第一外国语": 7, "政治理论课": 7, "专业外语": 7,
    "其他选修课": 10
}

# ==================== 以下代码不需要改 ====================


def get_cookie():
    """从脚本内置或环境变量获取Cookie，未配置时再让用户输入"""
    try:
        ck = globals().get("QIANGKE_COOKIE", "")
    except Exception:
        ck = ""
    if not ck:
        ck = os.environ.get("QIANGKE_COOKIE", "")
    if not ck:
        print("\n" + "=" * 50)
        print("  请按以下步骤获取Cookie：")
        print("=" * 50)
        print("  1. 打开浏览器，登录 http://yjsxk.fudan.edu.cn")
        print("  2. 按 F12 打开开发者工具")
        print("  3. 点 Application（应用）标签")
        print("  4. 左侧 Cookies -> yjsxk.fudan.edu.cn")
        print("  5. 复制所有Cookie的Name=Value，用分号连接")
        print("  6. 格式示例：")
        print("     _WEU=xxxxx; GS_SESSIONID=xxxxx; JSESSIONID=xxxxx; route=xxxxx")
        print("=" * 50)
        print()
        ck = input("请粘贴你的Cookie（粘贴后按回车）：").strip()
    if not ck:
        print("错误：Cookie不能为空！")
        os._exit(1)
    return ck


def request(ck, classification, course_ids, csrf_token):
    global cnt
    for course_id in course_ids:
        url = "http://" + target + "/yjsxkapp/sys/xsxkappfudan/xsxkCourse/choiceCourse.do?_=" + str(
            int(time.time() * 1000))

        headers = {
            "Cookie": ck.replace("\n", "").strip(),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "http://yjsxk.fudan.edu.cn/yjsxkapp/sys/xsxkappfudan/xsxkHome/gotoChooseCourse.do",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "http://yjsxk.fudan.edu.cn"
        }

        data = {
            "bjdm": course_id,
            "lx": str(course_classification_dict[classification]),
            "bqmc": classification,
            "csrfToken": csrf_token
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=3)
        except requests.exceptions.Timeout:
            print("[{}] {} - 请求超时，重试".format(
                datetime.datetime.now().strftime("%H:%M:%S"), course_id))
            return "cache", None
        except requests.exceptions.RequestException as e:
            print("[{}] {} - 网络错误: {}".format(
                datetime.datetime.now().strftime("%H:%M:%S"), course_id, e))
            return "cache", None

        try:
            data = json.loads(response.text)
            msg = data.get("msg", "")
            code = data.get("code", -1)
            if code == 1 or "选课成功" in msg:
                print("\n[{}] 选课成功！课程：{}，时间：{}".format(
                    datetime.datetime.now().strftime("%H:%M:%S"), course_id,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                print("继续抢其他课...", end="")
                return "success", course_id
            elif "缓存" in msg:
                with cnt_lock:
                    cnt += 1
                    c = cnt
                if c % 5 == 0:
                    print("[{}] {} - {}".format(
                        datetime.datetime.now().strftime("%H:%M:%S"), course_id, msg))
                return "cache", None
            elif "容量已满" in msg or "已满" in msg or "暂未释放" in msg or "不在" in msg or "不可选" in msg:
                with cnt_lock:
                    cnt += 1
                print("[{}] {} - 已满，尝试下一门".format(
                    datetime.datetime.now().strftime("%H:%M:%S"), course_id))
                continue
            elif "冲突" in msg:
                print("[{}] {} - {}".format(
                    datetime.datetime.now().strftime("%H:%M:%S"), course_id, msg))
                continue
            elif "过期" in msg:
                try:
                    new_token = get_csrf_token()
                    with cached_token_lock:
                        cached_token = new_token
                    print("[{}] token已刷新".format(
                        datetime.datetime.now().strftime("%H:%M:%S")))
                except Exception:
                    pass
                with cnt_lock:
                    cnt += 1
                return "cache", None
            else:
                with cnt_lock:
                    cnt += 1
                    c = cnt
                if c % 5 == 0:
                    print("[{}] {} - {}".format(
                        datetime.datetime.now().strftime("%H:%M:%S"), course_id, msg))
                return "cache", None
        except Exception as e:
            print("无法提交，请检查Cookie: {}".format(e.__str__()))
            return "cache", None
    return "full", None


def convert_seconds(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    s = int(s % 60)
    return h, m, s


def wait_until(target_time):
    now = datetime.datetime.now()
    if now > target_time:
        print("\n开始时间已过，立即开始抢课！")
        return

    wait_seconds = (target_time - now).total_seconds()
    hours, minutes, seconds = convert_seconds(wait_seconds)
    print("\n当前时间：{}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("将在 {}小时 {}分 {}秒 后开始抢课".format(hours, minutes, seconds))
    print("请耐心等待，不要关闭此窗口...\n")
    if wait_seconds > 1.5:
        time.sleep(wait_seconds - 1.0)
    while datetime.datetime.now() < target_time:
        pass


def get_csrf_token():
    url_token = "http://" + target + "/yjsxkapp/sys/xsxkappfudan/xsxkHome/gotoChooseCourse.do"
    try:
        current_ck = ck.replace("\n", "").strip()
    except Exception:
        current_ck = (globals().get("QIANGKE_COOKIE", "") or os.environ.get("QIANGKE_COOKIE", "")).replace("\n", "").strip()
    headers = {
        "Cookie": current_ck,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "http://yjsxk.fudan.edu.cn/yjsxkapp/sys/xsxkappfudan/xsxkHome/gotoChooseCourse.do"
    }
    try:
        response_token = requests.get(url_token, headers=headers, timeout=5)
    except requests.exceptions.RequestException as e:
        raise RuntimeError("网络请求失败: {}".format(e))
    match = re.search(r'id="csrfToken" value=\'([a-f0-9]{32})\'', response_token.text)
    csrf_token = match.group(1) if match else None
    if csrf_token is None or csrf_token == "":
        raise RuntimeError("Cookie已过期，请重新获取")
    return csrf_token


def killer(deadline):
    now = datetime.datetime.now()
    if now > deadline:
        deadline += datetime.timedelta(days=1)
    while datetime.datetime.now() < deadline:
        try:
            get_csrf_token()
        except Exception as e:
            print("\n[{}] {}".format(datetime.datetime.now().strftime("%H:%M:%S"), e.__str__()))
            os._exit(0)
        time.sleep(5)
    print("\n到达结束时间，抢课结束。当前时间：{}".format(
        datetime.datetime.now().strftime("%H:%M:%S")))
    os._exit(0)


def prefetch_token(target_time):
    """后台线程：提前获取并持续刷新csrfToken缓存"""
    global cached_token
    now = datetime.datetime.now()
    prefetch_start = target_time - datetime.timedelta(minutes=2)
    if now < prefetch_start:
        wait_s = (prefetch_start - now).total_seconds()
        print("[{}] token预获取将在{}后开始".format(
            datetime.datetime.now().strftime("%H:%M:%S"),
            prefetch_start.strftime("%H:%M:%S")))
        time.sleep(wait_s)

    print("[{}] 开始预获取csrfToken...".format(
        datetime.datetime.now().strftime("%H:%M:%S")))
    while True:
        try:
            token = get_csrf_token()
            with cached_token_lock:
                cached_token = token
        except Exception as e:
            print("[{}] token预获取失败: {}".format(
                datetime.datetime.now().strftime("%H:%M:%S"), e.__str__()))
        time.sleep(1)


def grab_group(group):
    """单个线程：抢一组课程，使用缓存的csrfToken"""
    classification = group[0]
    course_ids = group[1:]

    while course_ids:
        with cached_token_lock:
            csrf_token = cached_token

        if csrf_token is None:
            time.sleep(0.5)
            continue

        status, course_id = request(ck, classification, course_ids, csrf_token)
        if status == "success":
            course_ids.remove(course_id)
        elif status == "full":
            print("[{}] {} 类别下所有课程已满，跳过".format(
                datetime.datetime.now().strftime("%H:%M:%S"), classification))
            break
        elif status == "cache":
            time.sleep(0.2)


def main():
    wait_until(start_time)
    print("=" * 50)
    print("  开始抢课！当前时间：{}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("  多线程并发模式")
    print("=" * 50)

    threads = []
    for group in classification_and_course_ids:
        if len(group) > 1:
            t = threading.Thread(target=grab_group, args=(group,), daemon=True)
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

    print("\n" + "=" * 50)
    print("  所有课程已处理完毕！")
    print("  请登录选课网站确认结果")
    print("  当前时间：{}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    print("=" * 50)


if __name__ == "__main__":
    print("=" * 50)
    print("  复旦大学研究生抢课程序")
    print("=" * 50)

    ck = get_cookie()

    print("\nCookie已获取，正在验证...")
    try:
        token = get_csrf_token()
        print("验证通过！csrfToken: {}".format(token))
    except RuntimeError as e:
        print("错误：{}".format(e))
        print("请重新获取Cookie后重试")
        os._exit(1)

    start_time = datetime.datetime.now().replace(hour=START_HOUR, minute=START_MINUTE, second=START_SECOND, microsecond=0)
    end_time = datetime.datetime.now().replace(hour=END_HOUR, minute=END_MINUTE, second=END_SECOND, microsecond=0)

    print("\n一切就绪，等待抢课时间...")
    threading.Thread(target=killer, args=(end_time,), daemon=True).start()
    threading.Thread(target=prefetch_token, args=(start_time,), daemon=True).start()
    main()
    os._exit(0)
