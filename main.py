import pyotp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*', max_decode_size=10000000) # 파일 전송을 위해 용량 확장
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

user_sessions = {} # { sid: {"nickname": "...", "room": "..."} }
rooms_db = {}      # { "방이름": "OTP_Secret" }

@sio.event
async def create_room(sid, data):
    room_name = data.get('room')
    if not room_name: return
    if room_name in rooms_db:
        await sio.emit('join_fail', {'msg': "이미 존재하는 방 이름입니다."}, to=sid)
        return
    
    rooms_db[room_name] = pyotp.random_base32()
    totp = pyotp.TOTP(rooms_db[room_name], interval=60)
    await sio.emit('display_otp', {'code': totp.now()}, to=sid)
    await sio.emit('create_success', {'room': room_name}, to=sid)

@sio.event
async def join_with_otp(sid, data):
    room = data.get('room')
    otp_code = data.get('code')
    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room], interval=60)
        if totp.verify(otp_code):
            await sio.enter_room(sid, room)
            await sio.emit('join_success', {'room': room}, to=sid)
            await sio.emit('display_otp', {'code': totp.now()}, to=sid)
        else:
            await sio.emit('join_fail', {'msg': "OTP가 틀렸습니다."}, to=sid)
    else:
        await sio.emit('join_fail', {'msg': "방이 없습니다."}, to=sid)

@sio.event
async def set_nickname(sid, data):
    nickname = data.get('nickname', '').strip()
    room = data.get('room')
    
    # [수정] 중복 닉네임 체크 (현재 방에 있는 사람 기준)
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
        new_code = totp.now()
        await sio.emit('display_otp', {'code': new_code}, room=room)

@sio.event
async def send_secure_msg(sid, data):
    user_info = user_sessions.get(sid)
    if not user_info: return
    
    await sio.emit('receive_secure_msg', {
        'msg': data.get('msg'),
        'sender': user_info['nickname'],
        'type': data.get('type', 'text'),
        'fileName': data.get('fileName'),
        'fileType': data.get('fileType')
    }, room=user_info['room'])

@sio.event
async def leave_room(sid, data):
    user_info = user_sessions.get(sid)
    if user_info:
        room = user_info['room']
        nick = user_info['nickname']
        await sio.leave_room(sid, room)
        del user_sessions[sid]
        await sio.emit('notification', {'msg': f"'{nick}'님이 퇴장했습니다."}, room=room)
    await sio.emit('leave_success', to=sid)