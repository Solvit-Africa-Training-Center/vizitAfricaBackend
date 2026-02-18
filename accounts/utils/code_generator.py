from secrets import randbelow

from django.conf import settings

def generate_verification_code(n=6):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    # secrets.randbelow returns 0-limi
    return range_start + randbelow(range_end - range_start + 1)