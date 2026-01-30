from enum import Enum

class PermissionChoicesSchema(str, Enum):
    # Role
    GET_ROLES = "get_roles"
    GET_USER_ROLES = "get_user_roles"
    ASSIGN_ROLE_TO_USER = "assign_role_to_user"
    REMOVE_ROLE_FROM_USER = "remove_role_from_user"
    # Bank Account
    CREATE_ACCOUNT = "create_account"
    ACTIVATE_ACCOUNT = "activate_account"
    CREATE_DEPOSIT = "create_deposit"
    CREATE_WITHDRAWAL = "create_withdrawal"
    
    # Card
    CREATE_VIRTUAL_CARD = "create_virtual_card"
    ACTIVATE_CARD = "activate_card"
    BLOCK_CARD = "block_card"
    DELETE_VIRTUAL_CARD = "delete_virtual_card"
    TOP_UP_CARD = "top_up_card"
    # Transaction
    INITIATE_MONEY_TRANSFER = "initiate_money_transfer"
    COMPLETE_MONEY_TRANSFER = "complete_money_transfer"
    VIEW_TRANSACTION_HISTORY = "view_transaction_history"
    REVIEW_TRANSACTION = "review_transaction"
    GET_RISK_HISTORY = "get_risk_history"
    GENERATE_STATEMENT = "generate_statement"
    # Fraud/ Risk
    REVIEW_FRAUD_CASE = "review_fraud_case"
    VIEW_RISK_HISTORY = "view_risk_history"
    # Profile 
    CREATE_PROFILE = "create_profile"
    VIEW_MY_PROFILE = "view_my_profile"
    UPDATE_MY_PROFILE = "update_my_profile"
    VIEW_ALL_PROFILES = "view_all_profiles"
    # Profile Image
    UPLOAD_PROFILE_IMAGE = "upload_profile_image"
    VIEW_UPLOAD_STATUS = "view_upload_status"
    # Next of Kin
    VIEW_NEXT_OF_KIN = "view_next_of_kin"
    CREATE_NEXT_OF_KIN = "create_next_of_kin"
    UPDATE_NEXT_OF_KIN = "update_next_of_kin"
    DELETE_NEXT_OF_KIN = "delete_next_of_kin"
    # AI
    TRAIN_MODEL_WITH_DEFAULTS = "ai_train_model_with_defaults"
    TRAIN_MODEL = "ai_train_model"
    LIST_MODELS = "ai_list_models"
    GET_MODEL = "ai_get_model"
    GET_MODEL_STATUS = "ai_get_model_status"
    EVALUATE_MODEL = "ai_evaluate_model"
    DEPLOY_MODEL = "ai_deploy_model"
    AUTO_DEPLOY = "ai_auto_deploy"


