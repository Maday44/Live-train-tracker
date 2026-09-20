from collections import defaultdict
from math import ceil
from datetime import datetime
from flask import request


def paginate(items, set_per_page=25):
    page = request.args.get("page", 1, type=int)
    per_page = set_per_page
    begin = (page - 1) * per_page
    page_items = items[begin : begin + per_page]
    total_pages = ceil(len(items) / per_page) if items else 1

    return {
        "items": page_items,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total": len(items),
    }


def train_count_for_days(trains):
    train_count_for_days = defaultdict(int)
    for train in trains:
        day_date = train.get("date")

        if day_date:
            train_count_for_days[day_date] += 1

    return train_count_for_days


def categorised_trains(paginated):
    categorised_trains = defaultdict(list)

    for train in paginated:
        day_date = train.get("date")

        if day_date:
            categorised_trains[day_date].append(train)

    # Sort dates in reverse (newest date group first)
    return dict(sorted(categorised_trains.items(), reverse=True))
