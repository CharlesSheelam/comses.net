import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DrfValidationError

from core.models import Institution, MemberProfile
from core.serializers import TagSerializer, MarkdownField
from library.serializers import RelatedCodebaseSerializer

from .models import (FeaturedContentItem, UserMessage)

logger = logging.getLogger(__name__)


class FeaturedContentItemSerializer(serializers.ModelSerializer):
    image = serializers.SlugRelatedField(read_only=True, slug_field='file')

    class Meta:
        model = FeaturedContentItem
        fields = ('image', 'caption', 'title',)


class UserMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMessage
        fields = ('message', 'user')


class MemberProfileListSerializer(serializers.ModelSerializer):
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True, format='%c')
    full_name = serializers.CharField(source='name')
    username = serializers.CharField(source='user.username')
    profile_url = serializers.URLField(source='get_absolute_url', read_only=True)
    tags = TagSerializer(many=True)
    avatar = serializers.SerializerMethodField()  # needed to materialize the FK relationship for wagtailimages
    bio = MarkdownField()
    research_interests = MarkdownField()

    def get_avatar(self, instance):
        request = self.context.get('request')
        if request and request.accepted_media_type != 'text/html':
            return instance.picture.get_rendition('fill-150x150').url if instance.picture else None
        return instance.picture

    class Meta:
        model = MemberProfile
        fields = ('date_joined', 'full_name', 'profile_url', 'tags', 'username', 'avatar', 'bio', 'research_interests',)


class MemberProfileSerializer(serializers.ModelSerializer):
    """
    FIXME: References library.Codebase so
    """
    # User fields
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True, format='%c')
    family_name = serializers.CharField(source='user.last_name')
    full_name = serializers.CharField(source='name', read_only=True)
    given_name = serializers.CharField(source='user.first_name')
    username = serializers.CharField(source='user.username', read_only=True)
    user_pk = serializers.IntegerField(source='user.pk', read_only=True)
    email = serializers.SerializerMethodField()

    # Followers
    follower_count = serializers.ReadOnlyField(source='user.following.count')
    following_count = serializers.ReadOnlyField(source='user.followers.count')

    codebases = RelatedCodebaseSerializer(source='user.codebases', many=True, read_only=True)

    # Institution
    institution_name = serializers.CharField(required=False)
    institution_url = serializers.URLField(required=False)

    # MemberProfile
    avatar = serializers.SerializerMethodField()  # needed to materialize the FK relationship for wagtailimages
    orcid_url = serializers.ReadOnlyField()
    github_url = serializers.ReadOnlyField()
    tags = TagSerializer(many=True)
    profile_url = serializers.URLField(source='get_absolute_url', read_only=True)
    bio = MarkdownField()
    research_interests = MarkdownField()

    def get_email(self, instance):
        request = self.context.get('request')
        if request and request.user.is_anonymous():
            return None
        else:
            return instance.email

    def get_avatar(self, instance):
        request = self.context.get('request')
        if request and request.accepted_media_type != 'text/html':
            return instance.picture.get_rendition('fill-150x150').url if instance.picture else None
        return instance.picture

    @transaction.atomic
    def update(self, instance, validated_data):
        raw_tags = TagSerializer(many=True, data=validated_data.pop('tags'))
        user = instance.user
        raw_user = validated_data.pop('user')
        user.first_name = raw_user['first_name']
        user.last_name = raw_user['last_name']
        user.email = self.initial_data['email']
        try:
            # FIXME: need to send email verification again via django-allauth
            validate_email(user.email)
            if User.objects.filter(email=user.email).exclude(pk=user.pk).exists():
                raise DrfValidationError({'email': "This email address is already taken"})
        except ValidationError as e:
            raise DrfValidationError({'email': e.messages})

        raw_institution = {'name': validated_data.pop('institution_name'),
                           'url': validated_data.pop('institution_url')}
        institution = instance.institution
        if institution:
            institution.name = raw_institution.get('name')
            institution.url = raw_institution.get('url')
            institution.save()
        else:
            institution = Institution.objects.create(**raw_institution)
            instance.institution = institution

        # Full members cannot downgrade their status
        if instance.full_member:
            validated_data['full_member'] = True
        else:
            validated_data['full_member'] = bool(self.initial_data['full_member'])

        user.save()
        obj = super().update(instance, validated_data)
        self.save_tags(instance, raw_tags)
        return obj

    @staticmethod
    def save_tags(instance, tags):
        if not tags.is_valid():
            raise serializers.ValidationError(tags.errors)
        db_tags = tags.save()
        instance.tags.clear()
        instance.tags.add(*db_tags)
        instance.save()

    class Meta:
        model = MemberProfile
        fields = (
            # User
            'date_joined', 'family_name', 'full_name', 'given_name', 'profile_url',
            'username', 'email', 'user_pk',
            # Follower
            'follower_count', 'following_count',
            'codebases',
            # institution
            'institution_name', 'institution_url',
            # MemberProfile
            'avatar', 'bio', 'name', 'degrees', 'full_member', 'tags', 'orcid_url', 'github_url', 'personal_url',
            'is_reviewer', 'professional_url', 'profile_url', 'research_interests',)
