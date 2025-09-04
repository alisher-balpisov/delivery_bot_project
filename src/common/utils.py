class Phone(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not v.startswith("+"):
            raise ValueError("Phone must start with +")
        return cls(v)
