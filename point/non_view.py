from .models import *

#학생이 현재 입찰 중인 좌석 찾기
def find_seat(student:Student):
    log = Log.objects.filter(log_concept_name='seat', log_student_id=student.id, activated=True)
    if log:
        log = log.get()
        seat_id = Concept.objects.get(concept_id=log.log_concept_id).obj_id
        print(seat_id)
        return Seat.objects.get(id=seat_id)
    else:
        return None

def fix_seat(student:Student, seat:Seat):
    if seat.status == 'u':
        return True
    room = seat.room
    SeatResult.objects.create(
        room_id = room.id,
        seat_num = seat.num,
        student_id = student.id
    )

    seat.status='u'
    seat.save()

    print('done')
    return False

def extra_home():
    room = list(Room.objects.order_by('-id').all())[0]