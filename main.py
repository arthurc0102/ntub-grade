import json
import re
import requests

from argparse import ArgumentParser, ArgumentTypeError
from bs4 import BeautifulSoup
from collections import OrderedDict


URL = 'http://140.131.110.76/JMobile_STD/AjaxPage/SRHGRD_Years_ajax.aspx'
STD_NO_PATTERN = \
    '(?P<night>[N|n]?)' \
    '(?P<year>[0-9]{2,3})' \
    '(?P<system>[1-9])' \
    '(?P<department>[1-9A-Za-z])' \
    '(?P<class>[0-9]?)' \
    '(?P<no>[0-9]{2})'


def std_no_type(std_no):
    pattern = re.compile(STD_NO_PATTERN)
    if not pattern.match(std_no):
        raise ArgumentTypeError('學號格式不符合')

    return std_no.upper()


def get_list(std_no):
    res = requests.post(URL, {'stdNo': std_no, 'flag': '歷年成績表頭檔'})
    if not res.ok:
        raise Exception('Request error with status {}'.format(res.status_code))

    if '查無歷年成績紀錄資料' in res.text:
        return None

    soup = BeautifulSoup(res.text, 'html.parser')
    detail_link = soup.select('li.Midli>a')[-1]
    params = re.findall(r'\((.*)\)', detail_link['onclick'])[0]
    year, term = [int(param) for param in params.split(',')]
    return year, term


def get_grade(std_no, year=None, term=None):
    res = requests.post(URL, {
        'StdNo': std_no,
        'strYears': year,
        'strTerm': term,
        'flag': '歷年成績細項科目檔',
    })

    if not res.ok:
        raise Exception('Request error with status {}'.format(res.status_code))

    if '查無選擇學年期歷年成績資料' in res.text:
        return []

    result = []
    soup = BeautifulSoup(res.text, 'html.parser')

    for item in soup.select('li.Midli'):
        klass_element = item.select_one('strong')
        credit_element, score_element = item.select('p:nth-last-child(-n+2)')

        klass = klass_element.text.split(':')[-1].strip()
        credit = credit_element.text.split(':')[-1].strip()
        score = score_element.text.split(':')[-1].strip()

        result.append({
            'class': klass,
            'credit': float(credit),
            'score': float(score),
        })

    return result


def get_grade_range(std_no, count=1, year=None, term=None):
    if not (year and term):
        result = get_list(std_no)
        if not result:
            return {}

        year = year or result[0]
        term = term or result[1]

    prefix, num = std_no[:-2], std_no[-2:]
    students = ['{}{:02}'.format(prefix, int(num)+i) for i in range(count)]

    grades = {}
    for student in students:
        result = get_grade(student, year, term)
        if not result:
            continue

        grades[student] = result

    return grades


def get_average(grades):
    score_sum = 0
    credit_sum = 0

    for grade in grades:
        if grade['score'] == 888.0:
            continue

        score_sum += grade['credit'] * grade['score']
        credit_sum += grade['credit']

    return round(score_sum / credit_sum, 2)


def main():
    parser = ArgumentParser(description='北商成績查詢小工具')
    parser.add_argument(dest='std_no', help='學號', type=std_no_type)  # NOQA
    parser.add_argument('-c', '--count', dest='count', help='查詢筆數 (預設 1 筆)', type=int, default=1)  # NOQA
    parser.add_argument('-y', '--year', dest='year', help='學年 (要查詢的學年，若省略則用這學年)', type=int)  # NOQA
    parser.add_argument('-t', '--term', dest='term', help='學期 (要查詢的學年，若省略則用這學期)', type=int)  # NOQA
    parser.add_argument('-s', '--sort', dest='sort', help='按照名次排序', action='store_true')  # NOQA
    parser.add_argument('-d', '--detail', dest='detail', help='顯示各科的分數', action='store_true')  # NOQA
    parser.add_argument('--json', dest='to_json', help='轉換成 JSON 格式 (一律輸出各科分數並使用學號排序)', action='store_true')  # NOQA

    args = parser.parse_args()
    result = get_grade_range(args.std_no, args.count, args.year, args.term)

    if not result:
        print('查無結果')

    avg_grades = {}
    for s, g in result.items():
        avg_grades[s] = {'grade': g, 'average': get_average(g)}

    if args.to_json:
        print(json.dumps(avg_grades, indent=4))
        return

    avg_grades = avg_grades.items()

    if args.sort:
        avg_grades = sorted(
            avg_grades,
            key=lambda x: x[1]['average'],
            reverse=True
        )

    avg_grades_len = len(avg_grades)
    for i, grade_info in enumerate(avg_grades, 1):
        std_no = grade_info[0]
        grade = grade_info[1]['grade']
        average = grade_info[1]['average']

        prefix = '{:02}. '.format(i) if avg_grades_len > 1 else ''
        print('{}{}: {:.2f}'.format(prefix, std_no, average))

        if not args.detail:
            continue

        [print('  - {}: {:.2f}'.format(k['class'], k['score'])) for k in grade]

        if i != avg_grades_len:
            print()


if __name__ == '__main__':
    main()
