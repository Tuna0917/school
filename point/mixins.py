"""권한 믹스인과 데코레이터.

예전에는 클래스 기반 뷰 대부분에 권한 검사가 아예 없었다. 학생 A가
`/student/3/update`로 남의 이름을 바꿀 수 있었고, 로그인하지 않은 사람도
프리셋을 삭제할 수 있었다. 여기에 모아 두고 모든 뷰에 명시적으로 붙인다.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .services import DomainError


def is_staff(user):
    return bool(user.is_authenticated and user.is_staff)


def student_of(user):
    """user에 연결된 Student. 없으면 None (선생님/관리자 계정)."""
    if not user.is_authenticated:
        return None
    return getattr(user, "student", None)


class LoginThenForbidMixin(UserPassesTestMixin):
    """비로그인은 로그인 페이지로, 로그인했지만 권한이 없으면 403.

    `raise_exception = True`만 켜면 두 경우가 모두 403이 되어, 그냥 로그인이
    풀린 학생에게 "접근 금지"를 보여주게 된다. 반대로 끄면 권한 없는 학생을
    로그인 페이지로 계속 돌려보내 무한 루프처럼 느껴진다. 둘을 나눈다.
    """

    def handle_no_permission(self):
        self.raise_exception = self.request.user.is_authenticated
        return super().handle_no_permission()


class StaffRequiredMixin(LoginThenForbidMixin):
    """선생님 전용 뷰."""

    def test_func(self):
        return is_staff(self.request.user)


class LoggedInMixin(LoginRequiredMixin):
    """로그인만 요구하는 뷰."""


class OwnerOrStaffMixin(LoginThenForbidMixin):
    """본인 또는 선생님만 접근 가능. `get_object()`가 Student를 반환해야 한다."""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if is_staff(user):
            return True
        return self.get_object() == student_of(user)


def staff_required(view):
    """함수형 뷰용. 학생/외부인에게는 403."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_staff(request.user):
            raise PermissionDenied("선생님만 사용할 수 있는 기능입니다.")
        return view(request, *args, **kwargs)

    return wrapper


def student_required(view):
    """학생 계정 전용 (선생님 계정에는 Student가 없다)."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if student_of(request.user) is None:
            raise PermissionDenied("학생 계정으로 로그인해야 합니다.")
        return view(request, *args, **kwargs)

    return wrapper


def handle_domain_error(redirect_to):
    """DomainError를 메시지로 바꿔 사용자에게 보여준다.

    도메인 규칙 위반은 버그가 아니라 정상적인 사용자 실수이므로 500이 아니라
    안내 메시지로 처리한다.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except DomainError as exc:
                messages.error(request, str(exc))
                target = (
                    redirect_to(request, *args, **kwargs)
                    if callable(redirect_to)
                    else redirect_to
                )
                return redirect(target)

        return wrapper

    return decorator
