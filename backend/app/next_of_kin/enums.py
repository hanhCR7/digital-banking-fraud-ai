from enum import Enum

class RelationshipTypeEnum(str, Enum):
    # Loại quan hệ
    Spouse = "Spouse" # Vợ/Chồng
    Parent = "Parent" # Cha/Mẹ
    Sibling = "Sibling" # Anh/Chị/Em
    Child = "Child" # Con
    Other = "Other" # Khác