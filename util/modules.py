import aiohttp
from rich import print
from aiohttp import ClientConnectionError, TooManyRedirects, ClientProxyConnectionError, ClientTimeout
import json
import asyncio
import time


class TwitterActions:
    BASE_HEADERS = {
        'authority': 'twitter.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'dnt': '1',
        'pragma': 'no-cache',
        'referer': 'https://twitter.com/',
        'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
    }

    RETRIES = 5

    def __init__(self, ct0, auth, proxy=None):
        self.ct0 = ct0
        self.auth = auth
        self.proxy = proxy
        self.session = None

    async def initialize(self):
        self.session = aiohttp.ClientSession()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.session:
            await self.session.close()

    async def _make_request(self, method, url, json_data=None, params=None, data=None, headers=None, timeout=5):
        headers = headers or self.BASE_HEADERS.copy()
        headers['x-csrf-token'] = self.ct0
        self.session.cookie_jar.update_cookies(
            {'auth_token': self.auth, 'ct0': self.ct0})

        session_methods = {
            'GET': self.session.get,
            'POST': self.session.post,
            'PUT': self.session.put,
            'DELETE': self.session.delete,
            'PATCH': self.session.patch,
        }

        for attempt in range(self.RETRIES):
            try:
                async with session_methods[method](url, json=json_data if json_data else None, data=data if data else None, params=params if params else None, headers=headers, proxy=self.proxy, timeout=timeout) as resp:
                    if resp.status == 200:
                        try:
                            return resp.status, await resp.text()
                        except Exception as e:
                            return resp.status, None
                    elif resp.status == 401:
                        print(
                            f"[red][X] Unauthorized request: Token might be dead.")
                    elif resp.status in [400, 403, 404]:
                        print(f"[red][X] Error {resp.status}: {await resp.text()}")
                    else:
                        print(
                            f"[red][X] Unexpected status code: {resp.status}")
                    return resp.status, None
            except (ClientConnectionError, TooManyRedirects, ClientProxyConnectionError, Exception) as err:
                print(
                    f"[red][X] Error on attempt {attempt + 1}/{self.RETRIES}: [white]{err}")
                await asyncio.sleep(0)
                if attempt + 1 == self.RETRIES:
                    return None, None

    async def validate_account(self):
        status_code, response_data = await self._make_request('POST', 'https://twitter.com/i/api/1.1/account/update_profile.json')

        status_map = {
            200: ("bold green", "VALID"),
            "https://twitter.com/account/access": ("bold cyan", "LOCKED"),
            "/i/flow/consent_flow": ("bold yellow", "CONSENT"),
            "is suspended and": ("bold red", "SUSPENDED")
        }

        status_color, status_text = "bold red", "DEAD"

        if response_data:
            data = json.loads(response_data)

            # Check for various status conditions
            if status_code == 200:
                status_color, status_text = status_map[200]
            elif "https://twitter.com/account/access" in response_data:
                status_color, status_text = status_map["https://twitter.com/account/access"]
            elif "/i/flow/consent_flow" in response_data:
                status_color, status_text = status_map["/i/flow/consent_flow"]
            elif "is suspended and" in response_data:
                status_color, status_text = status_map["is suspended and"]

            # Check for 'screen_name' and 'followers_count'
            screen_name = data.get('screen_name')

            return status_code, screen_name
        else:
            print(
                f"[{status_color}][X] Token is dead (no response data): [white]{self.auth}")
            return status_text, None

    async def like(self, target, screen_name):
        json_data = {
            'variables': {
                'tweet_id': target,
            },
            'queryId': 'lI07N6Otwv1PhnEgXILM7A',
        }
        response = await self._make_request('POST', 'https://twitter.com/i/api/graphql/lI07N6Otwv1PhnEgXILM7A/FavoriteTweet', json_data=json_data)
        status, response_data = response
        # print(status, response_data)
        if "Done" in str(response_data):
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Liked The Tweet: [white]{target}")
            return True
        elif "has already" in str(response_data):
            print(
                f"[bold gold3][*] [white]{screen_name} [bold gold3]([white]{self.auth}[bold gold3]) has already liked the tweet: [white]{target}")
            return True
        else:
            print(
                f"[red][X] {screen_name} ({self.auth}) Failed to Like the Tweet: [white]{target}")
            return False

    async def retweet(self, target, screen_name):
        json_data = {
            'variables': {
                'tweet_id': target,
                'dark_request': False,
            },
            'queryId': 'ojPdsZsimiJrUGLR1sjUtA',
        }
        response = await self._make_request('POST', 'https://twitter.com/i/api/graphql/ojPdsZsimiJrUGLR1sjUtA/CreateRetweet', json_data=json_data)
        status, response_data = response
        # print(status, response_data)
        if status == 200:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Retweeted: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to Retweet: [white]{target}")
        return False

    async def bookmark(self, target, screen_name):
        json_data = {
            'variables': {
                'tweet_id': target,
                'dark_request': False,
            },
            'queryId': 'aoDbu3RHznuiSkQ9aNM67Q',
        }
        response = await self._make_request('POST', 'https://twitter.com/i/api/graphql/aoDbu3RHznuiSkQ9aNM67Q/CreateBookmark', json_data=json_data)
        status, response_data = response
        # print(status, response_data)
        if "Done" in response_data:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Bookmarked: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to Bookmark: [white]{target}")
        return False

    async def reply(self, target, screen_name, message):

        json_data = {
            'variables': {
                'tweet_text': message,
                'reply': {
                    'in_reply_to_tweet_id': target,
                    'exclude_reply_user_ids': [],
                },
                'dark_request': False,
                'media': {
                    'media_entities': [],
                    'possibly_sensitive': False,
                },
                'semantic_annotation_ids': [],
            },
            'features': {
                'tweetypie_unmention_optimization_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': False,
                'tweet_awards_web_tipping_enabled': False,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'responsive_web_media_download_video_enabled': False,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
            'queryId': 'PIZtQLRIYtSa9AtW_fI2Mw',
        }

        response = await self._make_request('POST', 'https://twitter.com/i/api/graphql/PIZtQLRIYtSa9AtW_fI2Mw/CreateTweet', json_data=json_data)
        status, response_data = response
        # print(status, response_data)
        if "edits_remaining" in response_data:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Replied to: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to Reply: [white]{target}")
        return False

    async def quote(self, target, screen_name, message):
        json_data = {
            'variables': {
                'tweet_text': message,
                'attachment_url': f"https://twitter.com/x/status/{target}",
                'dark_request': False,
                'media': {
                    'media_entities': [],
                    'possibly_sensitive': False,
                },
                'semantic_annotation_ids': [],
            },
            'features': {
                'tweetypie_unmention_optimization_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'responsive_web_twitter_article_tweet_consumption_enabled': False,
                'tweet_awards_web_tipping_enabled': False,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'responsive_web_media_download_video_enabled': False,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
            },
            'queryId': 'PIZtQLRIYtSa9AtW_fI2Mw',
        }
        response = await self._make_request('POST', 'https://twitter.com/i/api/graphql/PIZtQLRIYtSa9AtW_fI2Mw/CreateTweet', json_data=json_data)
        status, response_data = response
        # print(status, response_data)
        if "quoted_status_permalink" in response_data:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Quoted: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to Retweet: [white]{target}")
        return False

    async def follow(self, target, screen_name):
        data = {
            'include_profile_interstitial_type': '1',
            'include_blocking': '1',
            'include_blocked_by': '1',
            'include_followed_by': '1',
            'include_want_retweets': '1',
            'include_mute_edge': '1',
            'include_can_dm': '1',
            'include_can_media_tag': '1',
            'include_ext_has_nft_avatar': '1',
            'include_ext_is_blue_verified': '1',
            'include_ext_verified_type': '1',
            'include_ext_profile_image_shape': '1',
            'skip_status': '1',
            'user_id': target,
        }

        headers = {
            'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'DNT': '1',
            'x-twitter-client-language': 'en',
            'x-csrf-token': self.ct0,
            'sec-ch-ua-mobile': '?0',
            'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            'content-type': 'application/x-www-form-urlencoded',
            'Referer': 'https://twitter.com/',
            'x-twitter-auth-type': 'OAuth2Session',
            'x-twitter-active-user': 'yes',
            'sec-ch-ua-platform': '"Windows"',
        }

        response = await self._make_request('POST', 'https://twitter.com/i/api/1.1/friendships/create.json', data=data, headers=headers)
        status, response_data = response
        # print(status, response_data)
        if status == 200:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) Followed: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to Follow: [white]{target}")
        return False

    # Thank you @postuwu <3

    async def views(self, target, screen_name):

        params = {
            "debug": "true",
            "log": json.dumps([
                {
                    "_category_": "client_event",
                    "format_version": 2,
                    "triggered_on": int(time.time() * 1000),
                    "tweet_id": target,
                    "items": [
                        {
                            "item_type": 0,
                            "id": target,
                            "author_id": "123",
                            "is_viewer_follows_tweet_author": False,
                            "is_tweet_author_follows_viewer": False,
                            "is_viewer_super_following_tweet_author": False,
                            "is_viewer_super_followed_by_tweet_author": False,
                            "is_tweet_author_super_followable": False,
                            "engagement_metrics": {
                                "reply_count": 0,
                                "retweet_count": 0,
                                "favorite_count": 0,
                                "quote_count": 0
                            }
                        }
                    ],
                    "event_namespace": {
                        "page": "tweet",
                        "action": "bottom",
                        "client": "m5"
                    },
                    "client_event_sequence_start_timestamp": int(time.time() * 1000),
                    "client_event_sequence_number": 10,
                    "client_app_id": "3033300"
                },
                {
                    "_category_": "client_event",
                    "format_version": 2,
                    "triggered_on": int(time.time() * 1000),
                    "items": [
                        {
                            "item_type": 0,
                            "id": target,
                            "position": 0,
                            "sort_index": "1",
                            "percent_screen_height_100k": 31346,
                            "author_id": "123",
                            "is_viewer_follows_tweet_author": False,
                            "is_tweet_author_follows_viewer": False,
                            "is_viewer_super_following_tweet_author": False,
                            "is_viewer_super_followed_by_tweet_author": False,
                            "is_tweet_author_super_followable": False,
                            "engagement_metrics": {
                                "reply_count": 0,
                                "retweet_count": 0,
                                "favorite_count": 0,
                                "quote_count": 0
                            }
                        }
                    ],
                    "event_namespace": {
                        "page": "tweet",
                        "component": "stream",
                        "action": "results",
                        "client": "m5"
                    },
                    "client_event_sequence_start_timestamp": int(time.time() * 1000),
                    "client_event_sequence_number": 11,
                    "client_app_id": "3033300"
                }
            ])
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
            "x-csrf-token": self.ct0
        }

        response = await self._make_request('POST', 'https://api.twitter.com/1.1/jot/client_event.json?keepalive=true', params=params, headers=headers)
        status, response_data = response
        # print(status, response_data)
        if status == 200:
            print(
                f"[bold chartreuse3][!] [white]{screen_name} [bold chartreuse3]([white]{self.auth}[bold chartreuse3]) viewed: [white]{target}")
            return True
        print(
            f"[red][X] {screen_name} ({self.auth}) Faild to View: [white]{target}")
        return False
