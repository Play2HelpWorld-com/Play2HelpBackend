from django.urls import path
from .views import CreateUser, SignInView, ListUserView, ValidateTokenView, GetFBUserInfo, GetMsUserInfo, GetGoogleUserInfo, verifyEmail, reSendVerificationEmail,forgetPassword, resetPassword
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
  path('create/', CreateUser.as_view(), name='create_user'),
  path('signin/', SignInView.as_view(), name='signin'),
  path('list/', ListUserView.as_view(), name='list_users'),
  path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
  path('validateUser/', ValidateTokenView.as_view(), name='validate_user'),
  path('getGoogleUsrInfo/', GetGoogleUserInfo, name='get_google_user_info'),
  path('getFbUsrInfo/', GetFBUserInfo, name='get_fb_user_info'),
  path('getMsUsrInfo/', GetMsUserInfo, name='get_ms_user_info'),
  path('verifyEmail/', verifyEmail, name='verify_email'),
  path('resendVerification/', reSendVerificationEmail, name='re_send_verification_email'),
  path('forgetPassword/', forgetPassword, name='forget_password'),
  path('resetPassword/', resetPassword, name='reset_password'),
]