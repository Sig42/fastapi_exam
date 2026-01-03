from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import categories, products, users, reviews, cart, orders


app = FastAPI(
    title="fastapi_online_store",
    version="0.1.0"
)

app.include_router(categories.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(cart.router)
app.include_router(orders.router)

app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/")
async def root():
    return {"message": "Oh, shit! Here we go again!"}
