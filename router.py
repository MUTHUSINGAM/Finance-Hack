import os
from typing import Dict, Any
from openai import OpenAI
from budget_manager import budget_manager, ModelType
from vector_store import query_documents
from dotenv import load_dotenv

# Load connection params
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_question(user_query: str) -> Dict[str, Any]:
    """
    Routes a user query through the RAG pipeline using a Try/Escalate mechanic.
    Always standardizes to a fast mini-model unless it inherently warrants escalation.
    
    Args:
        user_query (str): The natural language query from the user.
        
    Returns:
        Dict[str, Any]: A payload containing the resolved 'answer' or 'error', alongside 'model' metadata.
    """
    # 1. Retrieve RAG contexts
    results = query_documents([user_query], n_results=3)
    contexts = []
    if results and results.get("documents") and results["documents"][0]:
        contexts = results["documents"][0]
        
    context_text = "\n---\n".join(contexts) if contexts else "No relevant documents found."
    
    chart_instruction = (
        "\n\nABSOLUTE REQUIREMENT: If the user asks for a numerical trend, comparison, or time-series, you MUST append a JSON block at the very end of your response. "
        "It must be wrapped in ```chart-data ... ```. Failure to output this JSON block will break the system. Do not skip this step under any circumstances.\n"
        "Example format:\n"
        "```chart-data\n"
        "[\n"
        '  {"year": "2020", "CompanyA": 100, "CompanyB": 200},\n'
        '  {"year": "2021", "CompanyA": 150, "CompanyB": 250}\n'
        "]\n"
        "```"
    )
    
    system_prompt = (
        "You are a financial intelligence assistant. Given the following context, answer the user's query.\n"
        "If the query requires complex mathematical comparisons or deep multi-document reasoning that you cannot safely and confidently perform, "
        "output exactly and only the word 'ESCALATE'.\n\nContext:\n\n" + context_text + chart_instruction
    )

    # 2. Try with gpt-4o-mini
    model_to_use = budget_manager.get_current_model(ModelType.GPT4O_MINI)
    
    try:
        response = client.chat.completions.create(
            model=model_to_use.value,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
        )
        
        # Update budget
        budget_manager.add_cost(
            model_to_use, 
            response.usage.prompt_tokens, 
            response.usage.completion_tokens
        )
        
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {"error": str(e)}
    
    # 3. Escalate if needed and budget allows
    if answer == "ESCALATE":
        if budget_manager.can_use_expensive_model():
            print("Escalating to GPT-4o...")
            model_to_use = ModelType.GPT4O
            
            try:
                response_esc = client.chat.completions.create(
                    model=model_to_use.value,
                    messages=[
                        {"role": "system", "content": "You are a senior financial analyst. Answer this query comprehensively using the context:\n\n" + context_text + chart_instruction},
                        {"role": "user", "content": user_query}
                    ]
                )
                budget_manager.add_cost(
                    model_to_use, 
                    response_esc.usage.prompt_tokens, 
                    response_esc.usage.completion_tokens
                )
                return {"answer": response_esc.choices[0].message.content, "model": model_to_use.value}
            except Exception as e:
                return {"error": str(e)}
        else:
            return {"answer": "The query is too complex, but limits ($7.50 cutoff) have been reached. Unable to escalate.", "model": model_to_use.value}
            
    return {"answer": answer, "model": model_to_use.value}
