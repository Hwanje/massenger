import os
import pyotp
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# .env 파일 로드 (로컬 개발 환경용)
load_dotenv()

# 환경 변수에서 관리자 정보 가져오기 (Render 등 배포 환경 설정 필수)
ADMIN_ID = os.getenv("ADMIN_ID", "default_admin") # 설정 안 되어 있을 때의 기본값
ADMIN_PW = os.getenv("ADMIN_PW", "default_pw")

# Socket.io 서버 설정 (파일 전송을 위해 max_decode_size 확장)
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins='*', 
    max_decode_size=10000000  # 약 10MB까지 허용
)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

# 서버 메모리 DB
user_sessions = {}  # { sid: {"nickname": "...", "room": "..."} }
rooms_db = {}       # { "방이름": "OTP_Secret_Key" }

@sio.event
async def connect(sid, environ):
    print(f"✅ 클라이언트 연결됨: {sid}")

@sio.event
async def create_room(sid, data):
    room_name = data.get('room', '').strip()
    if not room_name: return
    
    # [수정] 방 이름 중복 체크
    if room_name in rooms_db:
        await sio.emit('join_fail', {'msg': "이미 존재하는 방 이름입니다."}, to=sid)
        return
    
    # 새 방 생성 및 OTP 키 발급
    rooms_db[room_name] = pyotp.random_base32()
    totp = pyotp.TOTP(rooms_db[room_name], interval=60)
    
    await sio.emit('display_otp', {'code': totp.now()}, to=sid)
    await sio.emit('create_success', {'room': room_name}, to=sid)

@sio.event
async def join_with_otp(sid, data):
    room = data.get('room', '').strip()
    otp_code = data.get('code', '').strip()
    
    # [관리자 비밀 트릭] ID/PW 일치 시 관리자 모드 진입
    if room == ADMIN_ID and otp_code == ADMIN_PW:
        await sio.emit('admin_auth_success', {'rooms': list(rooms_db.keys())}, to=sid)
        return

    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room], interval=60)
        if totp.verify(otp_code):
            await sio.enter_room(sid, room)
            await sio.emit('join_success', {'room': room}, to=sid)
            await sio.emit('display_otp', {'code': totp.now()}, to=sid)
        else:
            await sio.emit('join_fail', {'msg': "OTP 코드가 일치하지 않습니다."}, to=sid)
    else:
        await sio.emit('join_fail', {'msg': "존재하지 않는 방입니다."}, to=sid)

@sio.event
async def set_nickname(sid, data):
    nickname = data.get('nickname', '').strip()
    room = data.get('room')
    
    if not nickname or not room: return

    # [수정] 동일 방 내 중복 닉네임 체크
    for s_id, info in user_sessions.items():
        if info.get('room') == room and info.get('nickname') == nickname:
            await sio.emit('nickname_fail', {'msg': "이미 사용 중인 닉네임입니다."}, to=sid)
            return

    user_sessions[sid] = {"nickname": nickname, "room": room}
    await sio.emit('nickname_success', to=sid)
    await sio.emit('notification', {'msg': f"'{nickname}'님이 입장했습니다."}, room=room)

@sio.event
async def refresh_otp(sid, data):
    room = data.get('room')
    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room], interval=60)
        # 방 안의 모든 유저에게 동시에 새로운 OTP 전송 (동기화 해결)
        await sio.emit('display_otp', {'code': totp.now()}, room=room)

@sio.event
async def send_secure_msg(sid, data):
    user_info = user_sessions.get(sid)
    if not user_info: return
    
    # 텍스트, 파일 통합 전송 로직
    await sio.emit('receive_secure_msg', {
        'msg': data.get('msg'), # 암호화된 텍스트 또는 Base64 파일 데이터
        'sender': user_info['nickname'],
        'type': data.get('type', 'text'),
        'fileName': data.get('fileName'),
        'fileType': data.get('fileType')
    }, room=user_info['room'])

@sio.event
async def delete_room_admin(sid, data):
    # 관리자 전용 방 삭제 로직
    target_room = data.get('target_room')
    if target_room in rooms_db:
        del rooms_db[target_room]
        # 해당 방 유저들에게 알림 후 삭제 사실 전파
        await sio.emit('notification', {'msg': "관리자가 이 방을 폐쇄했습니다."}, room=target_room)
        # 관리자 화면 목록 갱신
        await sio.emit('admin_auth_success', {'rooms': list(rooms_db.keys())}, to=sid)

@sio.event
async def leave_room(sid, data=None):
    user_info = user_sessions.get(sid)
    if user_info:
        room = user_info['room']
        nick = user_info['nickname']
        await sio.leave_room(sid, room)
        del user_sessions[sid]
        await sio.emit('notification', {'msg': f"'{nick}'님이 퇴장했습니다."}, room=room)
    await sio.emit('leave_success', to=sid)

@sio.event
async def disconnect(sid):
    # 연결 끊김 시 세션 정리
    if sid in user_sessions:
        room = user_sessions[sid]['room']
        nick = user_sessions[sid]['nickname']
        del user_sessions[sid]
        await sio.emit('notification', {'msg': f"'{nick}'님의 연결이 끊겼습니다."}, room=room)
    print(f"❌ 클라이언트 연결 끊김: {sid}")

@app.get("/")
async def health_check():
    return {"status": "running", "admin_configured": ADMIN_ID != "default_admin"}