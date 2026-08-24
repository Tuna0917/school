"""입력 검증 전용 폼.

예전 뷰는 `int(request.POST['point'])`를 그대로 썼다. 값이 없거나 숫자가
아니면 500, 음수면 포인트가 늘어나는 버그가 됐다. 폼을 거치면 타입/범위
검증이 한 곳에 모이고 에러를 사용자에게 보여줄 수 있다.
"""

from django import forms

from .models import Preset, Student


class BootstrapMixin:
    """모든 필드에 form-control을 붙인다. 템플릿마다 수동으로 쓰지 않기 위함."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class BidForm(BootstrapMixin, forms.Form):
    """좌석 입찰."""

    point = forms.IntegerField(
        min_value=1,
        label="포인트",
        widget=forms.NumberInput(attrs={"min": 1}),
    )

    def __init__(self, *args, student=None, room=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.room = room
        field = self.fields["point"]
        if room is not None and room.minimum:
            field.min_value = room.minimum
            field.widget.attrs["min"] = room.minimum
            field.help_text = f"최소 {room.minimum}포인트"
        if student is not None:
            field.max_value = student.point
            field.widget.attrs["max"] = student.point

    def clean_point(self):
        point = self.cleaned_data["point"]
        if self.room is not None and self.room.minimum and point < self.room.minimum:
            raise forms.ValidationError(
                f"이 교실의 최소 입찰 포인트는 {self.room.minimum}입니다."
            )
        if self.student is not None and point > self.student.point:
            raise forms.ValidationError(
                f"포인트가 부족합니다. (보유 {self.student.point})"
            )
        return point


class PointChangeForm(BootstrapMixin, forms.Form):
    """선생님의 포인트 지급/차감. 음수(차감)도 허용한다."""

    point = forms.IntegerField(label="포인트")
    reason = forms.CharField(
        max_length=200, required=False, label="이유", strip=True
    )
    preset = forms.ModelChoiceField(
        queryset=Preset.objects.all(), required=False, label="프리셋"
    )

    def clean(self):
        cleaned = super().clean()
        preset = cleaned.get("preset")
        if preset is not None:
            # 프리셋을 골랐으면 프리셋 값이 우선한다.
            cleaned["point"] = preset.point
            cleaned["reason"] = cleaned.get("reason") or preset.name
        if cleaned.get("point") == 0:
            raise forms.ValidationError("0포인트는 지급할 수 없습니다.")
        return cleaned


class RoomCreateForm(BootstrapMixin, forms.Form):
    """새 교실 열기."""

    row = forms.IntegerField(
        min_value=1, max_value=20, label="한 줄에 놓을 좌석 수"
    )
    num = forms.IntegerField(min_value=1, max_value=200, label="전체 좌석 수")
    minimum = forms.IntegerField(
        min_value=1, initial=1, label="최소 입찰 포인트"
    )
    notice = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}), required=False, label="공지"
    )

    def clean(self):
        cleaned = super().clean()
        row, num = cleaned.get("row"), cleaned.get("num")
        if row and num and row > num:
            raise forms.ValidationError(
                "한 줄의 좌석 수가 전체 좌석 수보다 많을 수 없습니다."
            )
        return cleaned


class StudentBulkCreateForm(BootstrapMixin, forms.Form):
    """학생 계정 일괄 생성."""

    number = forms.IntegerField(
        min_value=1, max_value=100, label="만들 학생 수"
    )


class StudentForm(BootstrapMixin, forms.ModelForm):
    """학생 본인은 이름만, 선생님은 상태까지 수정할 수 있다.

    예전 StudentUpdateView는 `dispatch`에서 `self.fields`를 바꿨는데, 이는
    클래스 속성을 건드리는 방식이라 한 번 선생님이 접속하면 이후 학생 요청에도
    status 필드가 남아 학생이 스스로 '자퇴'로 바꿀 수 있었다.
    """

    class Meta:
        model = Student
        fields = ["name"]

    def __init__(self, *args, allow_status=False, **kwargs):
        super().__init__(*args, **kwargs)
        if allow_status:
            self.fields["status"] = forms.ChoiceField(
                choices=Student.STATUS, label="상태", initial=self.instance.status
            )
            self.fields["status"].widget.attrs.setdefault("class", "form-select")

    def save(self, commit=True):
        student = super().save(commit=False)
        if "status" in self.fields:
            student.status = self.cleaned_data["status"]
        if commit:
            student.save()
        return student
