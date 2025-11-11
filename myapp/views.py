# myapp/views.py
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.db import connection
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from lxml import etree
from .models import Student
from .forms import idpw
import os
import html
import subprocess



# 메인 선택 화면
def main(request):
    return render(request, 'index.html')


# 기존 index (하위 호환성)
def index(request):
    return render(request, 'index.html')


# 인증 DB 데이터 목록
def student_list(request):
    students = Student.objects.all()
    return render(request, 'list.html', {'students': students})


# 1. SQL Injection
def sql_injection(request):
    if request.method == 'POST':
        form = idpw(request.POST)
        mode = request.POST.get('mode', 'safe')

        if form.is_valid():
            user_id = form.cleaned_data['id']
            password = form.cleaned_data['pw']

            with connection.cursor() as cursor:
                if mode == 'vulnerable':
                    # ❌ 취약한 코드 - SQL Injection 가능
                    sql_query = f"SELECT * FROM myapp_student WHERE userID='{user_id}' AND password='{password}'"
                    try:
                        cursor.execute(sql_query)
                        results = cursor.fetchall()

                        context = {
                            'mode': mode,
                            'executed_sql': sql_query,
                            'results': [f"ID: {r[0]}, UserID: {r[1]}, Password: {r[2]}" for r in results],
                        }
                    except Exception as e:
                        context = {
                            'mode': mode,
                            'executed_sql': sql_query,
                            'results': [],
                            'message': f'SQL 실행 오류가 발생했습니다. 입력값을 확인해주세요.',
                            'error_detail': str(e) if mode == 'vulnerable' else None
                        }
                else:
                    # ✅ 안전한 코드 - Parameterized Query 사용
                    sql_query = "SELECT * FROM myapp_student WHERE userID=%s AND password=%s"
                    try:
                        cursor.execute(sql_query, (user_id, password))
                        results = cursor.fetchall()

                        context = {
                            'mode': mode,
                            'executed_sql': sql_query,
                            'params': f"({user_id}, {password})",
                            'results': [f"ID: {r[0]}, UserID: {r[1]}, Password: {r[2]}" for r in results],
                        }
                    except Exception as e:
                        context = {
                            'mode': mode,
                            'executed_sql': sql_query,
                            'params': f"({user_id}, {password})",
                            'results': [],
                            'message': 'SQL 실행 오류가 발생했습니다. 입력값을 확인해주세요.'
                        }

                return render(request, 'success.html', context)
    else:
        form = idpw()

    return render(request, 'sql_injection.html', {'form': form})


# 2. Code Injection
def code_injection(request):
    if request.method == 'POST':
        command = request.POST.get('command', '').strip()
        mode = request.POST.get('mode', 'safe')

        if not command:
            context = {
                'mode': mode,
                'executed_sql': '입력 없음',
                'results': [],
                'message': '실행할 명령어를 입력해주세요.'
            }
            return render(request, 'success.html', context)

        if mode == 'vulnerable':
            # ❌ 취약한 코드 - eval() 직접 사용
            try:
                result = eval(command)
                executed_sql = f"eval('{command}')"
                results = [f"결과: {result}"]
                message = None
                error_detail = None
            except SyntaxError as e:
                executed_sql = f"eval('{command}')"
                results = []
                message = "문법 오류가 발생했습니다. Python 문법을 확인해주세요."
                error_detail = f"SyntaxError: {str(e)}"
            except NameError as e:
                executed_sql = f"eval('{command}')"
                results = []
                message = "정의되지 않은 변수나 함수를 사용했습니다."
                error_detail = f"NameError: {str(e)}"
            except Exception as e:
                executed_sql = f"eval('{command}')"
                results = []
                message = f"실행 중 오류가 발생했습니다: {type(e).__name__}"
                error_detail = str(e)
        else:
            # ✅ 안전한 코드 - 입력값 검증
            if not all(c in '0123456789+-*/(). ' for c in command):
                executed_sql = "입력 검증 실패"
                results = []
                message = "특수문자나 함수 호출이 포함되어 있어 실행이 거부되었습니다."
                error_detail = f"허용되지 않은 문자가 포함됨: {command}"
            else:
                try:
                    result = eval(command, {"__builtins__": {}}, {})
                    executed_sql = f"eval('{command}') with restricted builtins"
                    results = [f"결과: {result}"]
                    message = None
                    error_detail = None
                except ZeroDivisionError:
                    executed_sql = f"eval('{command}')"
                    results = []
                    message = "0으로 나눌 수 없습니다."
                    error_detail = "ZeroDivisionError: division by zero"
                except Exception as e:
                    executed_sql = f"eval('{command}')"
                    results = []
                    message = "수식 계산 중 오류가 발생했습니다."
                    error_detail = f"{type(e).__name__}: {str(e)}"

        context = {
            'mode': mode,
            'executed_sql': executed_sql,
            'results': results,
            'message': message,
            'error_detail': error_detail if mode == 'vulnerable' else None
        }
        return render(request, 'success.html', context)

    return render(request, 'code_injection.html')


# 3. Directory Traversal
def directory_traversal(request):
    if request.method == 'POST':
        filename = request.POST.get('filename', '').strip()
        mode = request.POST.get('mode', 'safe')

        if not filename:
            context = {
                'mode': mode,
                'executed_sql': '입력 없음',
                'results': [],
                'message': '파일명을 입력해주세요.'
            }
            return render(request, 'success.html', context)

        base_dir = '/tmp/uploads/'

        try:
            os.makedirs(base_dir, exist_ok=True)
            test_file_path = os.path.join(base_dir, 'test.txt')
            if not os.path.exists(test_file_path):
                with open(test_file_path, 'w', encoding='utf-8') as f:
                    f.write('이것은 안전한 테스트 파일입니다.\n이 파일은 정상적으로 접근 가능합니다.')
        except Exception as e:
            context = {
                'mode': mode,
                'executed_sql': '테스트 환경 설정 실패',
                'results': [],
                'message': '테스트 환경을 준비하는 중 오류가 발생했습니다.'
            }
            return render(request, 'success.html', context)

        if mode == 'vulnerable':
            # ❌ 취약한 코드 - 경로 검증 없음
            file_path = base_dir + filename
            executed_sql = f"파일 경로: {file_path}"

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                results = [f"파일 내용:\n{content[:500]}"]
                message = None
                error_detail = None
            except FileNotFoundError:
                results = []
                message = f"파일을 찾을 수 없습니다: {filename}"
                error_detail = f"FileNotFoundError: {file_path}"
            except PermissionError:
                results = []
                message = "파일에 접근할 권한이 없습니다."
                error_detail = f"PermissionError: {file_path}"
            except UnicodeDecodeError:
                results = []
                message = "텍스트 파일이 아니거나 인코딩 오류가 발생했습니다."
                error_detail = "UnicodeDecodeError: 바이너리 파일이거나 인코딩 문제"
            except Exception as e:
                results = []
                message = f"파일을 읽을 수 없습니다: {type(e).__name__}"
                error_detail = str(e)
        else:
            # ✅ 안전한 코드 - 경로 검증
            if '..' in filename or '/' in filename or '\\' in filename:
                executed_sql = "입력 검증 실패"
                results = []
                message = "잘못된 파일명입니다. 경로 조작 문자(.., /, \\)가 포함되어 있습니다."
                error_detail = f"차단된 문자 포함: {filename}"
            else:
                file_path = os.path.join(base_dir, filename)
                real_path = os.path.realpath(file_path)
                real_base = os.path.realpath(base_dir)

                executed_sql = f"검증된 경로: {file_path}"

                if not real_path.startswith(real_base):
                    results = []
                    message = "접근이 거부되었습니다. 허용된 디렉토리 외부의 파일입니다."
                    error_detail = f"경로 벗어남: {real_path} not in {real_base}"
                else:
                    try:
                        with open(real_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        results = [f"파일 내용:\n{content[:500]}"]
                        message = None
                        error_detail = None
                    except FileNotFoundError:
                        results = []
                        message = f"파일을 찾을 수 없습니다: {filename}"
                        error_detail = None
                    except Exception as e:
                        results = []
                        message = f"파일을 읽을 수 없습니다: {type(e).__name__}"
                        error_detail = None

        context = {
            'mode': mode,
            'executed_sql': executed_sql,
            'results': results,
            'message': message,
            'error_detail': error_detail if mode == 'vulnerable' else None
        }
        return render(request, 'success.html', context)

    return render(request, 'directory_traversal.html')


# 4. Reflected XSS
def reflected_xss(request):
    name = request.GET.get('name', '')
    mode = request.GET.get('mode', '')

    context = {
        'name': name,
        'mode': mode,
    }
    return render(request, 'reflected_xss.html', context)


# 5. Stored XSS
stored_comments = []

def stored_xss(request):
    global stored_comments

    if request.method == 'POST':
        if request.POST.get('clear'):
            stored_comments = []
            return redirect('stored_xss')

        author = request.POST.get('author', '')
        comment = request.POST.get('comment', '')
        mode = request.POST.get('mode', 'safe')

        if author and comment:
            stored_comments.append({
                'author': author,
                'text': comment,
                'is_safe': mode == 'safe'
            })

        return redirect('stored_xss')

    context = {
        'comments': stored_comments,
    }
    return render(request, 'stored_xss.html', context)


# 6. DOM-based XSS
def dom_xss(request):
    return render(request, 'dom_xss.html')


# 7. Command Injection (OS Command Injection)
def command_injection(request):
    if request.method == 'POST':
        command = request.POST.get('command', '').strip()
        mode = request.POST.get('mode', 'safe')

        if not command:
            context = {
                'mode': mode,
                'executed_sql': '입력 없음',
                'results': [],
                'message': '실행할 명령어를 입력해주세요.'
            }
            return render(request, 'success.html', context)

        if mode == 'vulnerable':
            # ❌ 취약한 코드 - os.popen() 직접 사용
            try:
                import os
                result = os.popen(command).read()
                executed_sql = f"os.popen('{command}')"
                results = [f"결과:\n{result}"] if result else ["명령 실행 완료 (출력 없음)"]
                message = None
                error_detail = None
            except Exception as e:
                executed_sql = f"os.popen('{command}')"
                results = []
                message = f"명령 실행 중 오류가 발생했습니다: {type(e).__name__}"
                error_detail = str(e)
        else:
            # ✅ 안전한 코드 - 화이트리스트 방식
            allowed_commands = {
                'date': ['date'],
                'hostname': ['hostname'],
                'whoami': ['whoami'],
                'pwd': ['pwd'],
            }

            if command not in allowed_commands:
                executed_sql = "화이트리스트 검증 실패"
                results = []
                message = f"허용되지 않은 명령어입니다. 사용 가능한 명령어: {', '.join(allowed_commands.keys())}"
                error_detail = f"차단된 명령어: {command}"
            else:
                try:
                    import subprocess
                    result = subprocess.run(
                        allowed_commands[command],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        shell=False
                    )
                    executed_sql = f"subprocess.run({allowed_commands[command]}, shell=False)"
                    output = result.stdout if result.stdout else result.stderr
                    results = [f"결과:\n{output}"] if output else ["명령 실행 완료 (출력 없음)"]
                    message = None
                    error_detail = None
                except subprocess.TimeoutExpired:
                    executed_sql = f"subprocess.run({allowed_commands[command]})"
                    results = []
                    message = "명령 실행 시간이 초과되었습니다."
                    error_detail = "TimeoutExpired: 5초 초과"
                except Exception as e:
                    executed_sql = f"subprocess.run({allowed_commands[command]})"
                    results = []
                    message = f"명령 실행 중 오류가 발생했습니다: {type(e).__name__}"
                    error_detail = str(e)

        context = {
            'mode': mode,
            'executed_sql': executed_sql,
            'results': results,
            'message': message,
            'error_detail': error_detail if mode == 'vulnerable' else None
        }
        return render(request, 'success.html', context)

    return render(request, 'command_injection.html')


# 8. 위험한 파일 업로드 (실행 기능 포함)
uploaded_files = []


def file_upload(request):
    global uploaded_files

    if request.method == 'POST':
        # 모두 삭제
        if request.POST.get('clear'):
            for file_info in uploaded_files:
                file_path = file_info.get('path')
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            uploaded_files = []
            return redirect('file_upload')

        # 파일 실행
        if request.POST.get('execute'):
            file_index = int(request.POST.get('file_index', -1))
            cmd_param = request.POST.get('cmd', 'whoami').strip()

            if 0 <= file_index < len(uploaded_files):
                file_info = uploaded_files[file_index]
                file_path = file_info['path']

                # Python 파일인 경우 실행
                if file_path.endswith('.py'):
                    try:
                        # ❌ 취약한 코드 - 업로드된 Python 파일을 실행
                        result = subprocess.run(
                            ['python3', file_path, cmd_param],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        output = result.stdout if result.stdout else result.stderr

                        context = {
                            'mode': 'vulnerable',
                            'executed_sql': f"python3 {file_path} {cmd_param}",
                            'results': [f"실행 결과:\n{output}"] if output else ["실행 완료 (출력 없음)"],
                            'message': f"파일 실행 성공: {file_info['name']}",
                            'error_detail': None
                        }
                        return render(request, 'success.html', context)
                    except subprocess.TimeoutExpired:
                        context = {
                            'mode': 'vulnerable',
                            'executed_sql': f"python3 {file_path}",
                            'results': [],
                            'message': "파일 실행 시간이 초과되었습니다.",
                            'error_detail': "TimeoutExpired: 5초 초과"
                        }
                        return render(request, 'success.html', context)
                    except Exception as e:
                        context = {
                            'mode': 'vulnerable',
                            'executed_sql': f"python3 {file_path}",
                            'results': [],
                            'message': f"파일 실행 중 오류 발생: {type(e).__name__}",
                            'error_detail': str(e)
                        }
                        return render(request, 'success.html', context)
                else:
                    context = {
                        'mode': 'vulnerable',
                        'executed_sql': '',
                        'results': [],
                        'message': "Python 파일만 실행할 수 있습니다.",
                        'error_detail': f"파일 형식: {file_path.split('.')[-1]}"
                    }
                    return render(request, 'success.html', context)

        # 파일 업로드
        uploaded_file = request.FILES.get('upload_file')
        mode = request.POST.get('mode', 'safe')

        if not uploaded_file:
            context = {
                'mode': mode,
                'executed_sql': '파일 없음',
                'results': [],
                'message': '업로드할 파일을 선택해주세요.',
                'error_detail': None
            }
            return render(request, 'success.html', context)

        if mode == 'vulnerable':
            # ❌ 취약한 코드 - 파일 검증 없이 업로드
            try:
                upload_dir = os.path.join(settings.BASE_DIR, 'uploads')
                os.makedirs(upload_dir, exist_ok=True)

                fs = FileSystemStorage(location=upload_dir)
                filename = fs.save(uploaded_file.name, uploaded_file)
                file_path = fs.path(filename)

                uploaded_files.append({
                    'name': uploaded_file.name,
                    'size': uploaded_file.size,
                    'path': file_path,
                    'is_safe': False
                })

                executed_sql = f"파일 저장: {upload_dir}/{uploaded_file.name}"
                results = [
                    f"파일명: {uploaded_file.name}",
                    f"크기: {uploaded_file.size} bytes",
                    f"저장 경로: {file_path}",
                    f"⚠️ 이 파일은 검증 없이 업로드되었습니다!"
                ]
                message = "파일이 업로드되었습니다. (검증 없음)"
                error_detail = None
            except Exception as e:
                executed_sql = "파일 업로드 실패"
                results = []
                message = f"파일 업로드 중 오류가 발생했습니다: {type(e).__name__}"
                error_detail = str(e)
        else:
            # ✅ 안전한 코드 - 파일 검증 후 업로드
            max_size = 5 * 1024 * 1024
            if uploaded_file.size > max_size:
                executed_sql = "파일 크기 검증 실패"
                results = []
                message = f"파일 크기가 너무 큽니다. 최대 5MB까지 허용됩니다. (현재: {uploaded_file.size / 1024 / 1024:.2f}MB)"
                error_detail = f"파일 크기: {uploaded_file.size} bytes"
            else:
                allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt']
                file_ext = os.path.splitext(uploaded_file.name)[1].lower()

                if file_ext not in allowed_extensions:
                    executed_sql = "파일 확장자 검증 실패"
                    results = []
                    message = f"허용되지 않은 파일 형식입니다. 허용된 확장자: {', '.join(allowed_extensions)}"
                    error_detail = f"업로드 시도한 확장자: {file_ext}"
                else:
                    allowed_mimes = [
                        'image/jpeg', 'image/png', 'image/gif',
                        'application/pdf', 'text/plain'
                    ]
                    mime_type = uploaded_file.content_type

                    if mime_type not in allowed_mimes:
                        executed_sql = "MIME 타입 검증 실패"
                        results = []
                        message = f"허용되지 않은 파일 타입입니다. (MIME: {mime_type})"
                        error_detail = f"탐지된 MIME 타입: {mime_type}"
                    else:
                        try:
                            upload_dir = os.path.join(settings.BASE_DIR, 'uploads')
                            os.makedirs(upload_dir, exist_ok=True)

                            import uuid
                            safe_filename = f"{uuid.uuid4()}{file_ext}"

                            fs = FileSystemStorage(location=upload_dir)
                            filename = fs.save(safe_filename, uploaded_file)
                            file_path = fs.path(filename)

                            uploaded_files.append({
                                'name': uploaded_file.name,
                                'saved_name': safe_filename,
                                'size': uploaded_file.size,
                                'mime': mime_type,
                                'path': file_path,
                                'is_safe': True
                            })

                            executed_sql = f"파일 저장 (검증 완료): {upload_dir}/{safe_filename}"
                            results = [
                                f"원본 파일명: {uploaded_file.name}",
                                f"저장 파일명: {safe_filename}",
                                f"크기: {uploaded_file.size} bytes",
                                f"MIME 타입: {mime_type}",
                                f"저장 경로: {file_path}"
                            ]
                            message = "파일이 안전하게 업로드되었습니다."
                            error_detail = None
                        except Exception as e:
                            executed_sql = "파일 업로드 실패"
                            results = []
                            message = f"파일 업로드 중 오류가 발생했습니다: {type(e).__name__}"
                            error_detail = str(e)

        context = {
            'mode': mode,
            'executed_sql': executed_sql,
            'results': results,
            'message': message,
            'error_detail': error_detail if mode == 'vulnerable' else None
        }
        return render(request, 'success.html', context)

    context = {
        'uploaded_files': uploaded_files,
    }
    return render(request, 'file_upload.html', context)


# 9. Open Redirect
def open_redirect(request):
    if request.method == 'GET':
        url = request.GET.get('url', '')
        mode = request.GET.get('mode', '')

        if url and mode:
            if mode == 'vulnerable':
                # ❌ 취약한 코드 - URL 검증 없이 리다이렉트 허용
                from urllib.parse import urlparse
                parsed = urlparse(url)

                context = {
                    'mode': mode,
                    'executed_sql': f"redirect('{url}')",
                    'results': [
                        f"🔴 위험! 검증 없이 리다이렉트가 허용되었습니다!",
                        f"목적지 URL: {url}",
                        f"도메인: {parsed.netloc if parsed.netloc else '(상대 경로)'}",
                        f"프로토콜: {parsed.scheme if parsed.scheme else '(없음)'}",
                        f"⚠️ 실제 환경에서는 이 페이지 없이 바로 리다이렉트됩니다! 사용자는 피싱 사이트로 이동했는지도 모를 수 있습니다!",
                    ],
                    'message': '취약한 코드: URL 검증 없이 리다이렉트 허용됨',
                    'redirect_url': url  # 실제 리다이렉트할 URL
                }
                return render(request, 'success.html', context)
            else:
                # ✅ 안전한 코드 - 화이트리스트 검증
                ALLOWED_DOMAINS = [
                    'example.com',
                    'trusted-site.com',
                    'mycompany.com'
                ]

                # 상대 경로만 허용 (도메인이 없는 경우)
                if url.startswith('/') and not url.startswith('//'):
                    context = {
                        'mode': mode,
                        'executed_sql': f"redirect('{url}') - 상대 경로 허용",
                        'results': [
                            f"✅ 안전: 내부 경로로 리다이렉트 허용",
                            f"목적지 URL: {url}",
                            f"유형: 상대 경로 (내부 페이지)",
                        ],
                        'message': '안전한 내부 경로입니다.',
                        'redirect_url': url
                    }
                    return render(request, 'success.html', context)

                # 절대 경로인 경우 화이트리스트 검증
                from urllib.parse import urlparse
                parsed = urlparse(url)

                if parsed.netloc in ALLOWED_DOMAINS:
                    context = {
                        'mode': mode,
                        'executed_sql': f"redirect('{url}') - 화이트리스트 통과",
                        'results': [
                            f"✅ 안전: 허용된 도메인으로 리다이렉트 허용",
                            f"목적지 URL: {url}",
                            f"도메인: {parsed.netloc}",
                            f"허용된 도메인 목록: {', '.join(ALLOWED_DOMAINS)}"
                        ],
                        'message': '화이트리스트에 등록된 안전한 도메인입니다.',
                        'redirect_url': url
                    }
                    return render(request, 'success.html', context)
                else:
                    context = {
                        'mode': mode,
                        'executed_sql': f"리다이렉트 시도: {url}",
                        'results': [
                            f"🛡️ 차단됨!",
                            f"시도한 URL: {url}",
                            f"시도한 도메인: {parsed.netloc}",
                            f"허용된 도메인 목록:",
                            *[f"  - {domain}" for domain in ALLOWED_DOMAINS]
                        ],
                        'message': f"'{parsed.netloc}'는 허용되지 않은 도메인입니다.",
                        'error_detail': f"화이트리스트에 없는 도메인: {parsed.netloc}"
                    }
                    return render(request, 'success.html', context)

    return render(request, 'open_redirect.html')


# 10. XML Injection
def xml_injection(request):
    if request.method == 'POST':
        user_name = request.POST.get('user_name', '').strip()
        mode = request.POST.get('mode', 'safe')

        if not user_name:
            context = {
                'mode': mode,
                'executed_sql': '입력 없음',
                'results': [],
                'message': '사용자 이름을 입력해주세요.'
            }
            return render(request, 'success.html', context)

        # XML 파일 경로
        xml_file = os.path.join(os.path.dirname(__file__), 'users.xml')

        # 예제 XML 파일이 없으면 생성
        if not os.path.exists(xml_file):
            sample_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<collection>
    <users>
        <user name="alice">
            <home>/home/alice</home>
        </user>
        <user name="bob">
            <home>/home/bob</home>
        </user>
        <user name="admin">
            <home>/root</home>
        </user>
    </users>
</collection>'''
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(sample_xml)

        if mode == 'vulnerable':
            # ❌ 취약한 코드 - 입력값을 직접 XPath 쿼리에 삽입
            try:
                parser = etree.XMLParser(resolve_entities=False)
                tree = etree.parse(xml_file, parser)
                root = tree.getroot()

                # 취약한 XPath 쿼리
                query = f"/collection/users/user[@name='{user_name}']/home/text()"
                elmts = root.xpath(query)

                executed_sql = query
                results = [f"홈 디렉토리: {home}" for home in elmts] if elmts else []
                message = f"{len(elmts)}개의 결과를 찾았습니다." if elmts else "결과를 찾을 수 없습니다."
                error_detail = None
            except etree.XPathEvalError as e:
                executed_sql = f"/collection/users/user[@name='{user_name}']/home/text()"
                results = []
                message = "XPath 쿼리 실행 중 오류가 발생했습니다."
                error_detail = f"XPathEvalError: {str(e)}"
            except Exception as e:
                executed_sql = f"/collection/users/user[@name='{user_name}']/home/text()"
                results = []
                message = f"XML 처리 중 오류가 발생했습니다: {type(e).__name__}"
                error_detail = str(e)
        else:
            # ✅ 안전한 코드 - Parameterized XPath 사용
            try:
                parser = etree.XMLParser(resolve_entities=False)
                tree = etree.parse(xml_file, parser)
                root = tree.getroot()

                # 안전한 XPath 쿼리 (자리표시자 사용)
                query = "/collection/users/user[@name = $paramname]/home/text()"
                elmts = root.xpath(query, paramname=user_name)

                executed_sql = f"{query} (paramname='{user_name}')"
                results = [f"홈 디렉토리: {home}" for home in elmts] if elmts else []
                message = f"{len(elmts)}개의 결과를 찾았습니다." if elmts else "결과를 찾을 수 없습니다."
                error_detail = None
            except Exception as e:
                executed_sql = query
                results = []
                message = f"XML 처리 중 오류가 발생했습니다: {type(e).__name__}"
                error_detail = None

        context = {
            'mode': mode,
            'executed_sql': executed_sql,
            'results': results,
            'message': message,
            'error_detail': error_detail if mode == 'vulnerable' else None
        }
        return render(request, 'success.html', context)

    return render(request, 'xml_injection.html')