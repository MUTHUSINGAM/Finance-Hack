import os
import json
from enum import Enum

class ModelType(str, Enum):
    """Enumeration of supported model types."""
    GPT4O_MINI = "gpt-4o-mini"
    GPT4O = "gpt-4o"

BUDGET_LIMIT = 7.50
COSTS = {
    ModelType.GPT4O_MINI: {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    ModelType.GPT4O: {"input": 5.00 / 1_000_000, "output": 15.00 / 1_000_000}
}
STATE_FILE = "budget_state.json"

class BudgetManager:
    """
    Manages budget tracking and limits for OpenAI API usage.
    Tracks accumulated costs and provides a circuit breaker to prevent overspending.
    """
    def __init__(self) -> None:
        """Initialize the budget manager and load previous state."""
        self.spent = 0.0
        self.load_state()

    def load_state(self) -> None:
        """Load the accumulated spending state from the persistence file."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    self.spent = json.load(f).get("spent", 0.0)
            except Exception:
                self.spent = 0.0

    def save_state(self) -> None:
        """Save the current accumulated spending state to the persistence file."""
        with open(STATE_FILE, "w") as f:
            json.dump({"spent": self.spent}, f)

    def add_cost(self, model: ModelType, input_tokens: int, output_tokens: int) -> float:
        """
        Calculates and records the cost of an API call.
        
        Args:
            model (ModelType): The model used for the API call.
            input_tokens (int): The number of prompt tokens used.
            output_tokens (int): The number of completion tokens used.
            
        Returns:
            float: The calculated cost of the request.
        """
        cost = (input_tokens * COSTS[model]["input"]) + (output_tokens * COSTS[model]["output"])
        self.spent += cost
        self.save_state()
        return cost

    def can_use_expensive_model(self) -> bool:
        """Check if the current budget allows for the use of more expensive models."""
        return self.spent < BUDGET_LIMIT
        
    def get_current_model(self, requested_model: ModelType = ModelType.GPT4O_MINI) -> ModelType:
        """
        Resolves the appropriate model to use based on requested tier and budget circuit breaker.
        
        Args:
            requested_model (ModelType): The desired model to use.
            
        Returns:
            ModelType: The safely authorized model.
        """
        if self.spent >= BUDGET_LIMIT:
            return ModelType.GPT4O_MINI
        return requested_model

budget_manager = BudgetManager()
