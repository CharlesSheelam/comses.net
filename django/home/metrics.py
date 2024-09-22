from core.models import MemberProfile, ComsesGroups
from library.models import CodebaseRelease, CodebaseReleaseDownload
from collections import defaultdict

from django.core.cache import cache
from django.db.models import Count, F
import pandas as pd


class Metrics:
    REDIS_METRICS_KEY = "all_comses_metrics"
    DEFAULT_METRICS_CACHE_TIMEOUT = 60 * 60 * 24 * 7  # 1 week
    MINIMUM_CATEGORY_COUNT = 10  # the threshold at which we group all other nominal values into an "other" category

    def get_all_data(self):
        data = cache.get(Metrics.REDIS_METRICS_KEY)
        if not data:
            return self.cache_all()
        return data

    def cache_all(self):
        """
        caches metrics data in redis
        """
        all_data = self.generate_metrics_data()
        cache.set(
            Metrics.REDIS_METRICS_KEY, all_data, Metrics.DEFAULT_METRICS_CACHE_TIMEOUT
        )
        return all_data

    def generate_metrics_data(self):
        """
        Returns all metrics data in a format amenable to HighCharts / frontend
        consumption.
        {
            totalMembers: {
                "title": "Total Members",
                "yLabel": "# Members",
                "startYear": 2008,
                "series": [{
                    "name": "total members",
                    "data": [40, 30, 30, 40, 40],
                }]
            },
            releasesByOs: {
                "title": "Models by OS",
                "yLabel": "# Releases",
                "startYear": 2008,
                "series": [
                {
                    name: "Windows",
                    data: [40, 30, 30, 40, 40, ...],
                },
                ...
                ]
            },
            releasesByPlatform : {
                "title": "Models by Platform",
                "yLabel": "# Releases",
                "startYear": 2008,
                "series": [
                {
                    name: "Ubuntu Mate",
                    data: [40, 30, 30, 40, 40],
                    start_year: 2008,
                }, ...
            ]},
        }
        """
        member_metrics, members_start_year = self.get_members_by_year_timeseries()
        release_metrics, release_start_year = self.get_release_metrics_timeseries()
        min_start_year = min(members_start_year, release_start_year)
        all_metrics = dict(
            startYear=min_start_year, **member_metrics, **release_metrics
        )
        return all_metrics

    def get_members_by_year_timeseries(self):
        """
        totalMembers: {
            "title": "Total Members",
            "yLabel": "# Members",
            "startYear": 2008,
            "series": [{
                "name": "total members",
                "data": [40, 30, 30, 40, 40],
            }]
        },
        """
        total_counts = list(
            MemberProfile.objects.public()
            .values(year=F("user__date_joined__year"))
            .annotate(total=Count("year"))
            .order_by("year")
        )
        full_member_counts = list(
            ComsesGroups.FULL_MEMBER.users()
            .values(year=F("date_joined__year"))
            .annotate(total=Count("year"))
            .order_by("year")
        )
        min_start_year = min(total_counts[0]["year"], full_member_counts[0]["year"])
        member_metrics = {
            "totalMembers": {
                "title": "Total Members",
                "yLabel": "# Members",
                "startYear": min_start_year,
                "series": [
                    {
                        "name": "Members",
                        "data": self.to_timeseries(total_counts, min_start_year),
                    }
                ],
            },
            "fullMembers": {
                "title": "Full Members",
                "yLabel": "# Members",
                "startYear": min_start_year,
                "series": [
                    {
                        "name": "Full Members",
                        "data": self.to_timeseries(full_member_counts, min_start_year),
                    }
                ],
            },
        }
        return member_metrics, min_start_year

    def get_release_metrics_timeseries(self):
        """
        releases_by_os: {
                "title": "Releases by OS",
                "yLabel": "# Releases",
                "startYear": 2008,
                "series": [
                {
                    name: "Windows",
                    data: [40, 30, 30, 40, 40, ...],
                },
                ...
                ]
            },
        """
        total_releases_by_year = list(
            CodebaseRelease.objects.public()
            .values(year=F("first_published_at__year"))
            .annotate(total=Count("year"))
            .order_by("year")
        )
        reviewed_releases_by_year = list(
            CodebaseRelease.objects.public(peer_reviewed=True)
            .values(year=F("first_published_at__year"))
            .annotate(total=Count("year"))
            .order_by("year")
        )
        release_downloads = list(
            CodebaseReleaseDownload.objects.values(year=F("date_created__year"))
            .annotate(total=Count("year"))
            .order_by("year")
        )
        min_start_year = total_releases_by_year[0]["year"]
        release_metrics = {
            "totalReleases": {
                "title": "Total Models",
                "yLabel": "# Models",
                "startYear": min_start_year,
                "series": [
                    {
                        "name": "Releases",
                        "data": self.to_timeseries(
                            total_releases_by_year, min_start_year
                        ),
                    }
                ],
            },
            "reviewedReleases": {
                "title": "Peer Reviewed Models",
                "yLabel": "# Releases",
                "startYear": min_start_year,
                "series": [
                    {
                        "name": "Peer Reviewed Models",
                        "data": self.to_timeseries(
                            reviewed_releases_by_year, min_start_year
                        ),
                    }
                ],
            },
            "totalDownloads": {
                "title": "Total Downloads",
                "yLabel": "# Downloads",
                "startYear": min_start_year,
                "series": [
                    {
                        "name": "Release Downloads",
                        "data": self.to_timeseries(release_downloads, min_start_year),
                    }
                ],
            },
            "releasesByOs": self.get_release_os_timeseries(min_start_year),
            "releasesByPlatform": self.get_release_platform_timeseries(
                min_start_year
            ),
            "releasesByLanguage": self.get_release_programming_language_timeseries(
                min_start_year
            ),
        }
        return release_metrics, min_start_year

    def get_release_os_timeseries(self, start_year):
        """
        Generate timeseries data for each possible release OS option

        Platform independent, macos, linux, windows, other

        releases_by_os: {
            "title": "Models by OS",
            "yLabel": "# Releases",
            "startYear": 2008,
            "series": [
            {
                name: "Windows",
                data: [40, 30, 30, 40, 40, ...],
            },
            ...
            ]
        },
        """
        os_metrics = list(
            CodebaseRelease.objects.public()
            .values(operating_systems=F("os"), year=F("first_published_at__year"))
            .annotate(count=Count("year"))
            .order_by("year")
        )

        return {
            "title": "Models by OS",
            "yLabel": "# Releases",
            "startYear": start_year,
            "series": self.convert_release_metrics_to_timeseries(
                os_metrics, start_year, "operating_systems"
            ),
        }

    def get_release_platform_timeseries(self, start_year):
        platform_metrics = list(
            CodebaseRelease.objects.public()
            .values(
                platform=F("platform_tags__name"), year=F("first_published_at__year")
            )
            .annotate(count=Count("year"))
            .order_by("year")
        )
        return {
            "title": "Models by Platform",
            "yLabel": "# Releases",
            "startYear": start_year,
            "series": self.convert_release_metrics_to_timeseries(
                platform_metrics, start_year, "platform"
            ),
        }

    def get_release_programming_language_timeseries(self, start_year):
        programming_language_metrics = list(
            CodebaseRelease.objects.public()
            .values(
                programming_language_names=F("programming_languages__name"),
                year=F("first_published_at__year"),
            )
            .annotate(count=Count("year"))
            .order_by("year")
        )

        #temporary fix to combine netlogo and logo
        combined_metrics = defaultdict(lambda: defaultdict(int))

        for metric in programming_language_metrics:
            language = metric['programming_language_names']
            if language in ['NetLogo', 'Logo']:
                language = 'NetLogo/Logo'
            
            year = metric['year']
            combined_metrics[year][language] += metric['count']
        
        flattened_metrics = []

        for year, languages in combined_metrics.items():
            for language, count in languages.items():
                flattened_metrics.append({
                    'programming_language_names': language,
                    'year': year,
                    'count': count
                })


        return {
            "title": "Models by Language",
            "yLabel": "# Releases",
            "startYear": start_year,
            "series": self.convert_release_metrics_to_timeseries(
                flattened_metrics, start_year, "programming_language_names"
            ),
        }

    def to_timeseries(self, queryset_data, start_year):
        """
        incoming queryset_data is a list of dicts with keys 'year' and 'total'

        return a timeseries with 0s for all missing years in-between
        """
        end_year = queryset_data[-1]["year"]
        queryset_dict = {item["year"]: item["total"] for item in queryset_data}
        data = []
        for year in range(start_year, end_year + 1):
            data.append(queryset_dict[year] if year in queryset_dict else 0)
        return data

    def convert_release_metrics_to_timeseries(
        self, metrics, start_year, category=None
    ):
        """
        Converts Django queryset metrics to a list of timeseries dicts e.g.,
        [{"name": "OS Counts", "data": [0, 37, 43, 14, 95, ...]}, ...]

        incoming metrics are a list of dicts in Django queryset values() format
        with the following schema:
        [
          ...
          {'operating_systems': 'macos', 'year': 2018, 'count': 18},
          {'operating_systems': 'windows', 'year': 2018, 'count': 54},
          {'operating_systems': 'linux', 'year': 2019, 'count': 8},
          {'operating_systems': 'windows', 'year': 2019, 'count': 75},
          {'operating_systems': 'platform_independent', 'year': 2019, 'count': 92},
          ...
        ]
        category is the column index to pivot on, if not set it is assumed to be the first column name

        The data may be sparse however, and we have to account for
        missing years, filling them with 0

                Year 2008  2009    2010 2011 2012 2013
        Windows        1   Nan->0   15   22   15     ..
        macOS
        """
        df = pd.DataFrame.from_records(metrics)
        df.replace([None], "None", inplace=True)
        if category is None:
            category = df.columns[0]
        if start_year < df["year"].min():
            # add an empty record for the start year
            start_year_df = pd.DataFrame(
                [["other", start_year, 0]], columns=[category, "year", "count"]
            )
            df = pd.concat([start_year_df, df])
        # set up a pivot table with year columns and row categories (e.g., os, platform, lang)
        categories_by_year = df.pivot_table(
            values="count",
            index=category,
            columns="year",
            aggfunc="first",
            fill_value=0,
        )
        full_date_range = pd.date_range(
            str(df["year"].min()), str(df["year"].max()), freq="YS"
        )
        # reindex the columns to include all years in the range
        categories_by_year = categories_by_year.reindex(
            columns=full_date_range.year, fill_value=0
        )

        # Extract rows whose max values are less than 10,
        # and integrate into an 'other' row
        included_categories_mask = (
            categories_by_year.max(axis=1) >= Metrics.MINIMUM_CATEGORY_COUNT
        )
        other_categories_mask = (
            categories_by_year.max(axis=1) < Metrics.MINIMUM_CATEGORY_COUNT
        )
        # build a new dataframe with the included categories and an 'other' row
        result_df = categories_by_year.loc[included_categories_mask]
        # this generates a SettingWithCopyWarning
        # See the caveats in the documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy"
        result_df.loc["other"] = categories_by_year.loc[other_categories_mask].sum(
            axis=0
        )

        # Convert result data frame into a list of Metrics Series objects
        category_list = result_df.index.drop_duplicates().tolist()
        return [
            {"name": category, "data": result_df.loc[category].tolist()}
            for category in category_list
        ]
