from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserSerializer, SignInSerializer, ListUserSerializer, AccessTokenSerializer, ThirdPartyUserSerializer
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework import generics, permissions
from .models import User
import requests
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import os
import random
import string
from users.utils.sendEmail import send_email;


class CreateUser(APIView):
  def post(self, request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
      serializer.save()
      user = serializer.instance
      verification_token = RefreshToken.for_user(user).access_token
      verification_url = f"{os.environ.get('FRONTEND_BASE_URL')}/accounts/verifyEmail?token={verification_token}"
      send_email(
        subject="Verify your email",
        recipient_list=[user.email],
        message=f"Please verify your email by clicking on the following link: {verification_url}"
      )
      return Response(serializer.data, status=status.HTTP_201_CREATED)
    # Extract the first error message
    errors = serializer.errors
    first_error = None
    for field, error_list in errors.items():
      first_error = error_list[0]
      break
    return Response({"error": first_error}, status=status.HTTP_400_BAD_REQUEST)

class SignInView(APIView):
  def post(self, request):
    serializer = SignInSerializer(data=request.data)
    if serializer.is_valid():
      user = serializer.validated_data['user']
      if not user.is_verified:
        return Response({"error": "Please verify your email before signing in"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
      refresh = RefreshToken.for_user(user)
      return Response({
        'refreshToken': str(refresh),
        'accessToken': str(refresh.access_token),
      }, status=status.HTTP_200_OK)
    errors = serializer.errors
    first_error = None
    for field, error_list in errors.items():
      first_error = error_list[0].__str__()
      break
    return Response({"error": first_error}, status=status.HTTP_400_BAD_REQUEST) 
  
class ListUserView(generics.ListAPIView):
  queryset = User.objects.all()
  serializer_class = ListUserSerializer
  permission_classes = [permissions.IsAuthenticated]

class ValidateTokenView(APIView):
  def post(self, request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
      return Response({"error": "Invalid token header"}, status=status.HTTP_400_BAD_REQUEST)
    
    token = auth_header.split(' ')[1]
    serializer = AccessTokenSerializer(data={'token': token})
    if serializer.is_valid():
      user = serializer.get_user()
      return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
  
def generate_random_password(length=12):
  characters = string.ascii_letters + string.digits + string.punctuation
  return ''.join(random.choice(characters) for i in range(length))
  
  
@api_view(['POST'])
def handleThrdProvUser(request, user):
  serializer = ThirdPartyUserSerializer(data=user)
  if serializer.is_valid():
    user_data = serializer.validated_data 
    email = user_data['email']
    name = user_data['name']
    try:
      user = User.objects.get(email=email)
    except User.DoesNotExist:
      password = generate_random_password()
      user = User.objects.create_user(email=email, name=name, password=password)
      user.is_verified = True
    refresh = RefreshToken.for_user(user)
    accessToken =  str(refresh.access_token)
    refreshToken = str(refresh)
    return Response({
      'refreshToken': refreshToken,
      'accessToken': accessToken,
      'user': UserSerializer(user).data
    }, status=status.HTTP_200_OK)
  return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def GetGoogleUserInfo(request):
  code = request.data.get('code')
  if not code:
    return Response({'error': 'Authorization code is required'}, status=status.HTTP_400_BAD_REQUEST)
  try:
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = f"{os.environ.get('FRONTEND_BASE_URL')}/{os.environ.get('GOOGLE_REDIRECT_URI')}"
    token_response = requests.post(
      f"https://oauth2.googleapis.com/token",
      data={
      'client_id': client_id,
      'client_secret': client_secret,
      'code': code,
      'grant_type': 'authorization_code',
      'redirect_uri': redirect_uri,
      },
      headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    # Enhanced error logging
    if token_response.status_code != 200:
      error_data = token_response.json()
      return Response({
        'error': error_data.get('error_description', 'Authentication failed'),
        'details': {
          'redirect_uri': redirect_uri,
          'error_code': error_data.get('error', 'unknown')
        }
      }, status=status.HTTP_400_BAD_REQUEST)
    
    token_response.raise_for_status()
    access_token = token_response.json().get('access_token')

    user_info_response = requests.get(
      f"https://www.googleapis.com/oauth2/v3/userinfo",
      headers={'Authorization': f'Bearer {access_token}'}
    )
    user_info_response.raise_for_status()
    user_data = user_info_response.json()
    user = {
      'name': user_data['name'],
      'email': user_data['email']
    }
    return handleThrdProvUser(request._request, user)
  except requests.RequestException as e:
    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def GetFBUserInfo(request):
  code = request.data.get('code')
  if not code:
    return Response({'error': 'Authorization code is required'}, status=status.HTTP_400_BAD_REQUEST)
  try:
    app_id = os.environ.get('FACEBOOK_APP_ID')
    app_secret = os.environ.get('FACEBOOK_APP_SECRET')
    redirect_uri = f"{os.environ.get('FRONTEND_BASE_URL')}/accounts/fbCallback"

    # Exchange authorization code for access token
    token_response = requests.get(
      f"https://graph.facebook.com/v10.0/oauth/access_token?client_id={app_id}&redirect_uri={redirect_uri}&client_secret={app_secret}&code={code}"
    )
    token_response.raise_for_status()
    access_token = token_response.json().get('access_token')

    # Fetch user information from Facebook API
    user_info_response = requests.get(
      f"https://graph.facebook.com/me?fields=id,name,email&access_token={access_token}"
    )
    user_info_response.raise_for_status()
    user = user_info_response.json()
    return handleThrdProvUser(request._request, user)
  except requests.RequestException as e:
    return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
  

@api_view(['POST'])
def GetMsUserInfo(request):
  code = request.data.get('code')
  if not code:
    return Response(
      {'error': 'Authorization code is required'}, 
      status=status.HTTP_400_BAD_REQUEST
    )
  
  try:
    client_id = os.environ.get('MICROSOFT_CLIENT_ID')
    client_secret = os.environ.get('MICROSOFT_CLIENT_SECRET')
    redirect_uri = f"{os.environ.get('FRONTEND_BASE_URL')}/{os.environ.get('MICROSOFT_REDIRECT_URI')}"
    print('the redirect uri is', redirect_uri)
    
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    token_data = {
      'client_id': client_id,
      'client_secret': client_secret,
      'code': code,
      'redirect_uri': redirect_uri,
      'grant_type': 'authorization_code',
      'scope': 'User.Read openid profile email'
    }
    
    token_response = requests.post(
      token_url,
      data=token_data,
      headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    # Enhanced error logging
    if token_response.status_code != 200:
      error_data = token_response.json()
      
      return Response({
        'error': error_data.get('error_description', 'Authentication failed'),
        'details': {
          'redirect_uri': redirect_uri,
          'scopes': token_data['scope'],
          'error_code': error_data.get('error', 'unknown')
        }
      }, status=status.HTTP_401_UNAUTHORIZED)
      
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    
    if not access_token:
      return Response(
        {'error': 'No access token received'}, 
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
      )
    
    # Fetch user information
    user_info_response = requests.get(
      "https://graph.microsoft.com/v1.0/me",
      headers={
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
      }
    )
    user_info_response.raise_for_status()
    user_data = user_info_response.json()
    
    user = {
      'name': user_data['displayName'],
      'email': user_data['mail']
    }
    return handleThrdProvUser(request._request, user)
  except requests.RequestException as e:
    print(f"Request failed: {str(e)}")
    return Response(
      {'error': str(e)}, 
      status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
        
      
@api_view(['POST'])
def verifyEmail(request):
  token = request.data.get('token')
  if not token:
    return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
  try:
    access_token = AccessToken(token)
    user = User.objects.get(id=access_token['user_id'])
    user.is_verified = True
    user.save()
    return Response({"message": "Email verified successfully"}, status=status.HTTP_200_OK)
  except Exception as e:
    print(f"Error verifying email: {str(e)}")
    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
  

@api_view(['POST'])
def reSendVerificationEmail(request):
  email = request.data.get('email')
  if not email:
    return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
  
  try:
    user = User.objects.get(email=email)
    if user.is_verified:
      return Response({"message": "Email is already verified"}, status=status.HTTP_200_OK)
    
    verification_token = RefreshToken.for_user(user).access_token
    verification_url = f"{os.environ.get('FRONTEND_BASE_URL')}/accounts/verifyEmail?token={verification_token}"
    send_email(
      subject="Verify your email",
      recipient_list=[user.email],
      message=f"Please verify your email by clicking on the following link: {verification_url}"
    )
    return Response({"message": "Verification email sent successfully"}, status=status.HTTP_200_OK)
  except User.DoesNotExist:
    return Response({"error": "User with this email does not exist"}, status=status.HTTP_404_NOT_FOUND)
  except Exception as e:
    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
  
  
  
@api_view(['POST'])
def forgetPassword(request):
  email = request.data.get('email')
  if not email:
    return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
  
  try:
    user = User.objects.get(email=email)
    reset_token = RefreshToken.for_user(user).access_token
    reset_url = f"{os.environ.get('FRONTEND_BASE_URL')}/accounts/resetPassword?token={reset_token}"
    send_email(
      subject="Reset your password",
      recipient_list=[user.email],
      message=f"Please reset your password by clicking on the following link: {reset_url}"
    )
    return Response({"message": "Password reset email sent successfully"}, status=status.HTTP_200_OK)
  except User.DoesNotExist:
    return Response({"error": "User with this email does not exist"}, status=status.HTTP_404_NOT_FOUND)
  except Exception as e:
    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
  
  
  
@api_view(['POST'])
def resetPassword(request):
  token = request.data.get('token')
  password = request.data.get('password')
  if not token:
    return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
  if not password:
    return Response({"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)
  
  try:
    access_token = AccessToken(token)
    user = User.objects.get(id=access_token['user_id'])
    user.set_password(password)
    user.save()
    return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)
  except Exception as e:
    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)