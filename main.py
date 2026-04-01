import os
import pyotp
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import time

load_dotenv()

ADMIN_ID = os.getenv("ADMIN_ID", "admin")
ADMIN_PW = os.getenv("ADMIN_PW", "1234")

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', max_decode_size=10000000)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

# 서버 데이터 구조
user_sessions = {}  # { sid: {"nickname": "...", "room": "..."} }
rooms_db = {}       # { "방이름": {"secret": "...", "last_refresh": 0} }

@sio.event
async def create_room(sid, data):
    room_name = data.get('room', '').strip()
    if not room_name or room_name in rooms_db:
        await sio.emit('join_fail', {'msg': "방 이름이 올바르지 않거나 이미 존재합니다."}, to=sid)
        return
    
    # 방 생성 및 시크릿 할당
    rooms_db[room_name] = {
        "secret": pyotp.random_base32(),
        "last_refresh": 0
    }
    
    # [수정] 방장은 OTP 없이 즉시 입장
    await sio.enter_room(sid, room_name)
    await sio.emit('create_success', {'room': room_name}, to=sid)
    await sio.emit('join_success', {'room': room_name}, to=sid)
    print(f"방 생성 및 입장: {room_name}")

@sio.event
async def join_with_otp(sid, data):
    room = data.get('room', '').strip()
    otp_code = data.get('code', '').strip()
    
    if room == ADMIN_ID and otp_code == ADMIN_PW:
        # 관리자 정보 강화: 방 목록과 현재 접속자 수 포함
        room_info = [{"name": r, "count": len(sio.manager.rooms.get('/', {}).get(r, []))} for r in rooms_db.keys()]
        await sio.emit('admin_auth_success', {'rooms': room_info}, to=sid)
        return

    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room]["secret"], interval=60)
        if totp.verify(otp_code):
            await sio.enter_room(sid, room)
            await sio.emit('join_success', {'room': room}, to=sid)
        else:
            await sio.emit('join_fail', {'msg': "OTP 코드가 올바르지 않습니다."}, to=sid)
    else:
        await sio.emit('join_fail', {'msg': "존재하지 않는 방입니다."}, to=sid)

@sio.event
async def set_nickname(sid, data):
    nickname = data.get('nickname', '').strip()
    room = data.get('room')
    
    for s_id, info in user_sessions.items():
        if info.get('room') == room and info.get('nickname') == nickname:
            await sio.emit('nickname_fail', {'msg': "중복된 닉네임입니다."}, to=sid)
            return

    user_sessions[sid] = {"nickname": nickname, "room": room}
    await sio.emit('nickname_success', to=sid)
    await sio.emit('notification', {'msg': f"'{nickname}'님이 입장했습니다."}, room=room)

@sio.event
async def refresh_otp(sid, data):
    room = data.get('room')
    user = user_sessions.get(sid)
    if not room or not user or room not in rooms_db: return
    
    now = time.time()
    last = rooms_db[room]["last_refresh"]
    
    if now - last < 30:
        await sio.emit('notification', {'msg': f"갱신 대기 중입니다. ({int(30-(now-last))}초 남음)"}, to=sid)
        return

    rooms_db[room]["last_refresh"] = now
    totp = pyotp.TOTP(rooms_db[room]["secret"], interval=60)
    
    # 전원에게 갱신 알림 및 코드/타이머 동기화
    await sio.emit('notification', {'msg': f"📢 '{user['nickname']}'님이 OTP를 갱신했습니다."}, room=room)
    await sio.emit('display_otp', {'code': totp.now(), 'time_left': 60}, room=room)

@sio.event
async def delete_room_admin(sid, data):
    target = data.get('target_room')
    if target in rooms_db:
        await sio.emit('room_closed', {'msg': "관리자가 방을 폐쇄했습니다."}, room=target)
        del rooms_db[target]
        # 목록 새로고침용 데이터 전송
        room_info = [{"name": r, "count": 0} for r in rooms_db.keys()]
        await sio.emit('admin_auth_success', {'rooms': room_info}, to=sid)

@sio.event
async def disconnect(sid):
    if sid in user_sessions:
        room = user_sessions[sid]['room']
        nick = user_sessions[sid]['nickname']
        del user_sessions[sid]
        
        # 방에 남은 인원 확인
        remaining = [s for s, info in user_sessions.items() if info.get('room') == room]
        if not remaining and room in rooms_db:
            del rooms_db[room]
            print(f"🗑️ 빈 방 자동 삭제: {room}")
        else:
            await sio.emit('notification', {'msg': f"'{nick}'님이 나갔습니다."}, room=room)

@sio.event
async def send_secure_msg(sid, data):
    info = user_sessions.get(sid)
    if info:
        await sio.emit('receive_secure_msg', {
            'msg': data.get('msg'),
            'sender': info['nickname'],
            'type': data.get('type', 'text'),
            'fileName': data.get('fileName'),
            'fileType': data.get('fileType')
        }, room=info['room'])
@sio.event
async def send_global_notice(sid, data):
    msg = data.get('msg')
    if msg:
        await sio.emit('global_notice', {'msg': msg}) # 모든 접속자에게 브로드캐스트

