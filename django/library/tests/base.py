import io
import random
from uuid import UUID

from core.tests.base import ContentModelFactory, UserFactory
from library.fs import FileCategoryDirectories
from library.models import (
    Codebase,
    CodebaseRelease,
    License,
    ReleaseContributor,
    Contributor,
    PeerReviewInvitation,
    PeerReview,
    PeerReviewer,
)
from library.serializers import CodebaseSerializer


class CodebaseFactory(ContentModelFactory):
    model = Codebase
    serializer = CodebaseSerializer

    def __init__(self, submitter):
        super().__init__(submitter)
        self.id = 0

    def get_default_data(self):
        uuid = UUID(int=random.getrandbits(128))
        return {
            "title": "Wolf Sheep Predation",
            "description": "Wolf sheep predation model in NetLogo with grass",
            "uuid": uuid,
            "identifier": str(uuid),
            "submitter": self.submitter,
        }

    def data_for_create_request(self, **overrides):
        codebase = self.create_unsaved(**overrides)
        codebase.id = 0
        serialized = CodebaseSerializer(codebase).data
        del serialized["id"]
        return serialized


class ContributorFactory:
    def __init__(self, user):
        self.user = user

    def get_default_data(self, user):
        if user is None:
            user = self.user
        return {
            "given_name": user.first_name,
            "family_name": user.last_name,
            "type": "person",
            "email": user.email,
            "user": user,
        }

    def create(self, **overrides) -> Contributor:
        kwargs = self.get_default_data(overrides.get("user"))
        kwargs.update(overrides)
        return Contributor.objects.create(**kwargs)


class ReleaseContributorFactory:
    def __init__(self, codebase_release):
        self.codebase_release = codebase_release
        self.index = 0

    def get_default_data(self):
        defaults = {"release": self.codebase_release, "index": self.index}
        self.index += 1
        return defaults

    def create(self, contributor: Contributor, **overrides):
        kwargs = self.get_default_data()
        kwargs.update(overrides)
        return ReleaseContributor.objects.create(contributor=contributor, **kwargs)


class CodebaseReleaseFactory:
    def __init__(self, codebase, submitter=None):
        if submitter is None:
            submitter = codebase.submitter
        self.submitter = submitter
        self.codebase = codebase

    def get_default_data(self):
        return {
            "description": "Added rational utility decision making to wolves",
            "submitter": self.submitter,
            "codebase": self.codebase,
            "live": True,
        }

    def create(self, **defaults) -> CodebaseRelease:
        kwargs = self.get_default_data()
        kwargs.update(defaults)

        codebase = kwargs.pop("codebase")
        submitter = kwargs.pop("submitter")

        codebase_release = codebase.create_release(submitter=submitter)
        for k, v in kwargs.items():
            if hasattr(codebase_release, k):
                setattr(codebase_release, k, v)
            else:
                raise KeyError('Key "{}" is not a property of codebase'.format(k))
        codebase_release.save()
        return codebase_release


class PeerReviewFactory:
    def __init__(self, submitter, codebase_release):
        self.submitter = submitter
        self.codebase_release = codebase_release

    def get_default_data(self):
        return {"submitter": self.submitter, "codebase_release": self.codebase_release}

    def create(self, **defaults):
        kwargs = self.get_default_data()
        kwargs.update(defaults)

        review = PeerReview(**kwargs)
        review.save()
        return review


class PeerReviewInvitationFactory:
    def __init__(self, editor, reviewer, review):
        self.editor = editor
        self.review = review
        self.reviewer = reviewer

    def get_default_data(self):
        return {
            "candidate_reviewer": self.reviewer.member_profile,
            "reviewer": self.reviewer,
            "editor": self.editor,
            "review": self.review,
        }

    def create(self, **defaults):
        kwargs = self.get_default_data()
        kwargs.update(defaults)

        invitation = PeerReviewInvitation(**kwargs)
        invitation.save()
        return invitation


class ReviewSetup:
    @classmethod
    def setUpReviewData(cls):
        cls.user_factory = UserFactory()
        cls.editor = cls.user_factory.create().member_profile
        reviewer = cls.user_factory.create().member_profile
        cls.reviewer = PeerReviewer.objects.create(member_profile=reviewer)
        cls.submitter = cls.user_factory.create()

        cls.codebase_factory = CodebaseFactory(cls.submitter)
        cls.codebase = cls.codebase_factory.create()
        cls.codebase_release = cls.codebase.create_release(initialize=False)
        cls.review_factory = PeerReviewFactory(
            submitter=cls.codebase.submitter.member_profile,
            codebase_release=cls.codebase_release,
        )
        cls.review = cls.review_factory.create()


class ReleaseSetup:
    @classmethod
    def setUpPublishableDraftRelease(cls, codebase):
        draft_release = codebase.create_release(
            status=CodebaseRelease.Status.DRAFT,
            initialize=True,
        )
        draft_release.license = License.objects.create(name="MIT")
        draft_release.os = "Linux"
        draft_release.programming_languages.add("Python")
        contributor_factory = ContributorFactory(user=draft_release.submitter)
        release_contributor_factory = ReleaseContributorFactory(draft_release)
        contributor = contributor_factory.create()
        release_contributor_factory.create(contributor)

        code_file = io.BytesIO(b"print('hello world')")
        code_file.name = "some_code_file.py"
        docs_file = io.BytesIO(b"# Documentation")
        docs_file.name = "some_doc_file.md"
        fs_api = draft_release.get_fs_api()
        fs_api.add(content=code_file, category=FileCategoryDirectories.code)
        fs_api.add(content=docs_file, category=FileCategoryDirectories.docs)

        draft_release.save()

        return draft_release
