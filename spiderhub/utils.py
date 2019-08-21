# coding=utf-8


def get_meta_from_pagination(pagination):
    return {'page': pagination.page, 'pages': pagination.pages,
            'per_page': pagination.per_page, 'total': pagination.total,
            'has_prev': pagination.has_prev, 'has_next': pagination.has_next,
            'prev_num': pagination.prev_num, 'next_num': pagination.next_num}
