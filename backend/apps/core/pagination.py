"""Pagination defaults shared by every list endpoint."""

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """25 items per page, with a hard upper bound of 100."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
