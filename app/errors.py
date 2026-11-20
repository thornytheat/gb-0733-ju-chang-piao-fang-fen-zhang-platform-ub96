class Problem(Exception):
    def __init__(self, status, code, detail=None):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(code)


class RowError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)
