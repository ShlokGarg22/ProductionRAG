from app.services.llm import get_llm

llm = get_llm()

try:
    print("Sending request to Portkey...")
    response = llm.invoke("Hello, are you working?")
    print("Response:", response.content)
except Exception as e:
    print("Error:", e)
