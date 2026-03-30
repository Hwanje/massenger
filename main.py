import pyotp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

user_sessions = {}  # { sid: "닉네임" }
rooms_db = {}       # { "방이름": "OTP_Secret" }

@sio.event
async def connect(sid, environ):
    print(f"Connected: {sid}")

@sio.event
async def create_room(sid, data):
    room_name = data.get('room')
    if not room_name: return
    if room_name not in rooms_db:
        rooms_db[room_name] = pyotp.random_base32()
    
    sio.enter_room(sid, room_name)
    totp = pyotp.TOTP(rooms_db[room_name], interval=60)
    # 방 생성자에게 코드와 성공 알림 전송
    await sio.emit('display_otp', {'code': totp.now()}, to=sid)
    await sio.emit('join_success', {'room': room_name}, to=sid)

@sio.event
async def join_with_otp(sid, data):
    room = data.get('room')
    otp_code = data.get('code')
    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room], interval=60)
        if totp.verify(otp_code):
            sio.enter_room(sid, room)
            await sio.emit('join_success', {'room': room}, to=sid)
        else:
            await sio.emit('join_fail', {'msg': "OTP가 틀렸습니다."}, to=sid)
    else:
        await sio.emit('join_fail', {'msg': "방이 없습니다."}, to=sid)

@sio.event
async def set_nickname(sid, data):
    nickname = data.get('nickname', '익명')
    room = data.get('room')
    user_sessions[sid] = nickname
    # 방 전체에 알림
    await sio.emit('notification', {'msg': f"'{nickname}'님이 입장했습니다."}, room=room)

@sio.event
async def refresh_otp(sid, data):
    room = data.get('room')
    if room in rooms_db:
        totp = pyotp.TOTP(rooms_db[room], interval=60)
        # 갱신된 코드를 '방 전체'가 아닌 '요청한 사람'에게만 보냄 (보안상)
        await sio.emit('display_otp', {'code': totp.now()}, to=sid)

@sio.event
async def send_secure_msg(sid, data):
    nickname = user_sessions.get(sid, "익명")
    room = data.get('room')
    msg = data.get('msg')
    if room and msg:
        # 중요: room=room을 넣어 해당 방의 모든 sid에게 메시지 전송
        await sio.emit('receive_secure_msg', {
            'msg': msg, 
            'sender': nickname 
        }, room=room)

@sio.event
async def leave_room(sid, data):
    room = data.get('room')
    sio.leave_room(sid, room)
    await sio.emit('leave_success', to=sid)

@app.get("/")
async def health():
    return {"status": "Live"}
