from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from members.models import Members
from members.serializers import MemberSerializer
from tokens.models import TokenInfo
from tokens.serializers import TokenInfoSerializer

from .models import FrontendSite, Game, Score, TotalScore
from .serializers import ScoreSerializer, TotalScoreSerializer

User = get_user_model()

FRONTEND_SITE_ALIASES = {
    "weplah2help": FrontendSite.WEPLAY2HELP,
    "weplay2help": FrontendSite.WEPLAY2HELP,
    "weplay2health": FrontendSite.WEPLAY2HEALTH,
    "weplay2learn": FrontendSite.WEPLAY2LEARN,
    "weplay2love": FrontendSite.WEPLAY2LOVE,
    "weplay2work": FrontendSite.WEPLAY2WORK,
}

TRACKED_FRONTEND_SITES = [
    FrontendSite.WEPLAY2HELP,
    FrontendSite.WEPLAY2HEALTH,
    FrontendSite.WEPLAY2LEARN,
    FrontendSite.WEPLAY2LOVE,
    FrontendSite.WEPLAY2WORK,
]

FRONTEND_SITE_LABELS = {
    choice: label
    for choice, label in FrontendSite.choices
}


def normalize_frontend_site(value):
    if value is None:
        return FrontendSite.UNKNOWN
    return FRONTEND_SITE_ALIASES.get(str(value).strip().lower())


def build_leaderboard(queryset, limit=10):
    leaderboard_rows = (
        queryset
        .values("user", "user__name")
        .annotate(
            total_score=Coalesce(Sum("score"), 0),
            total_tokens=Coalesce(Sum("tokens"), 0.0),
            games_played=Count("game", distinct=True),
            site_count=Count("source_site", distinct=True),
        )
        .order_by("-total_score", "user__name")[:limit]
    )

    leaderboard = []
    for index, row in enumerate(leaderboard_rows, start=1):
        leaderboard.append({
            "rank": index,
            "user_id": row["user"],
            "user_name": row["user__name"],
            "total_score": row["total_score"],
            "total_tokens": round(float(row["total_tokens"]), 4),
            "games_played": row["games_played"],
            "site_count": row["site_count"],
        })
    return leaderboard


class SubmitScoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ScoreSerializer(data=request.data)
        print("the request.data is", request.data)

        game_name = request.data.get("game")
        source_site = normalize_frontend_site(request.data.get("source_site"))
        game = Game.objects.filter(name=game_name).first()
        score = request.data.get("score")
        tokens = request.data.get("tokens")

        if not source_site:
            return Response(
                {
                    "error": "source_site is invalid.",
                    "allowed_sites": [choice for choice, _ in FrontendSite.choices if choice != FrontendSite.UNKNOWN],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tokens = float(tokens)
        except (TypeError, ValueError):
            return Response({"error": "Tokens must be a number."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            score = int(score)
        except (TypeError, ValueError):
            return Response({"error": "Score must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        if not game_name or score < 0:
            return Response({"error": "Game is a required field."}, status=status.HTTP_400_BAD_REQUEST)

        if not game:
            return Response({"error": "Game not found in the db."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        existing_score = Score.objects.filter(user=user, game=game, source_site=source_site).first()
        existing_total_score = TotalScore.objects.filter(user=user).first()

        if existing_score:
            existing_score.score += score
            existing_score.tokens += tokens
            existing_score.save()
            score_response = {"message": "Score updated successfully"}
        else:
            if serializer.is_valid():
                serializer.save(user=user, game=game, source_site=source_site)
                score_response = {"message": "Score submitted successfully"}
            else:
                print("the serializer error is", serializer.errors)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if existing_total_score:
            existing_total_score.total_score += score
            existing_total_score.total_tokens += tokens
            existing_total_score.save()
        else:
            TotalScore.objects.create(user=user, total_score=score, total_tokens=tokens)

        return Response(score_response, status=status.HTTP_200_OK)


class ScoreListView(generics.ListAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ScoreSerializer

    def get_queryset(self):
        user = self.request.user
        source_site = normalize_frontend_site(self.request.query_params.get("source_site"))
        queryset = Score.objects.filter(user=user)
        if source_site:
            queryset = queryset.filter(source_site=source_site)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = {
            "scores": response.data
        }
        return response


class ListAllScores(generics.ListAPIView):
    serializer_class = ScoreSerializer

    def get_queryset(self):
        game_name = self.request.query_params.get("game")
        source_site = normalize_frontend_site(self.request.query_params.get("source_site"))
        game = Game.objects.filter(name=game_name).first()
        queryset = Score.objects.all()
        print("the game is", game)
        print("the source_site is", source_site)
        if not game or not source_site:
            return queryset.order_by("-score")
        if game:
            queryset = queryset.filter(game=game)
        if source_site:
            queryset = queryset.filter(source_site=source_site)
        return queryset.order_by("-score")


class SetClaimTokensView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        claimed_tokens = float(request.data.get("claimed_tokens"))
        last_claimed_date = request.data.get("last_claimed_date")
        game = request.data.get("game")
        source_site = normalize_frontend_site(request.data.get("source_site"))
        game_model = Game.objects.get(name=game)
        if not last_claimed_date:
            return Response({"error": "last claimed date is required"}, status=status.HTTP_400_BAD_REQUEST)
        if claimed_tokens is None:
            return Response({"error": "Claimed tokens are required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = request.user
            score_queryset = Score.objects.filter(user=user, game=game_model)
            if source_site:
                score_queryset = score_queryset.filter(source_site=source_site)
            if score_queryset.count() > 1:
                return Response(
                    {"error": "Multiple score rows found for this game. Please provide source_site."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            score_model = score_queryset.get()
            score_model.claimed_tokens += claimed_tokens
            score_model.last_claimed_date = last_claimed_date
            score_model.save()
            return Response({"message": "Tokens claimed successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetScoreDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        game_name = request.GET.get("gameName")
        try:
            game = Game.objects.get(name=game_name)
            token_info = TokenInfo.objects.get(id=game.tokenInfo.id)
            serializer = TokenInfoSerializer(token_info)
            return Response({
                "tokenInfo": serializer.data,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetTotalScoresView(APIView):
    def get(self, request):
        try:
            total_scores = TotalScore.objects.all().order_by("-total_score")
            serializer = TotalScoreSerializer(total_scores, many=True)
            return Response({
                "total_scores": serializer.data,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetMembersView(APIView):
    def get(self, request):
        try:
            member = Members.objects.all()
            serializer = MemberSerializer(member, many=True)
            return Response({
                "member": serializer.data,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetAllScoresWithTokenInfo(APIView):
    def get(self, request, *args, **kwargs):
        try:
            all_scores = Score.objects.all()
            scores_with_token_info = []

            if all_scores.exists():
                for score in all_scores:
                    try:
                        user_wallet_address = score.user.wallet_address
                        token_amount = score.tokens
                        token_address = score.game.tokenInfo.bnb_contract_address
                        scores_with_token_info.append({
                            "userWalletAddress": user_wallet_address,
                            "tokenAmount": token_amount,
                            "tokenAddress": token_address,
                            "sourceSite": score.source_site,
                            "game": score.game.name,
                        })
                    except AttributeError as attr_error:
                        print(f"Missing data for score ID {score.id}: {str(attr_error)}")
                print("Scores with token info:", scores_with_token_info)
            else:
                print("No scores found in the database.")

            return Response(scores_with_token_info, status=status.HTTP_200_OK)

        except Exception as e:
            print("An error occurred:", str(e))
            return Response({"error": "An error occurred while retrieving scores."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetWorldStatsView(APIView):
    def get(self, request):
        try:
            all_scores = Score.objects.exclude(source_site=FrontendSite.UNKNOWN)
            registered_users_total = User.objects.count()
            active_users_total = all_scores.values("user").distinct().count()
            total_score_entries = all_scores.count()
            total_games = Game.objects.count()

            master_leaderboard = build_leaderboard(all_scores)
            per_site_leaderboards = {}
            site_user_counts = []

            for site_key in TRACKED_FRONTEND_SITES:
                site_scores = all_scores.filter(source_site=site_key)
                site_leaderboard = build_leaderboard(site_scores, limit=10)
                site_total_score = site_scores.aggregate(
                    total=Coalesce(Sum("score"), 0)
                )["total"]
                site_user_count = site_scores.values("user").distinct().count()
                site_score_entries = site_scores.count()

                per_site_leaderboards[site_key] = {
                    "site": site_key,
                    "label": FRONTEND_SITE_LABELS.get(site_key, site_key),
                    "entries": site_leaderboard,
                }

                site_user_counts.append({
                    "site": site_key,
                    "label": FRONTEND_SITE_LABELS.get(site_key, site_key),
                    "active_users": site_user_count,
                    "score_entries": site_score_entries,
                    "total_score": site_total_score,
                })

            return Response(
                {
                    "summary": {
                        "registered_users_total": registered_users_total,
                        "active_users_total": active_users_total,
                        "tracked_sites_count": len(TRACKED_FRONTEND_SITES),
                        "total_score_entries": total_score_entries,
                        "total_games": total_games,
                    },
                    "user_counts": {
                        "all_sites_total": registered_users_total,
                        "active_players_total": active_users_total,
                        "sites": site_user_counts,
                    },
                    "leaderboards": {
                        "master": master_leaderboard,
                        "sites": per_site_leaderboards,
                    },
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
