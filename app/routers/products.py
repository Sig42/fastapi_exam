from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Product as ProductSchema, ProductCreate, ProductList
from app.db_depends import get_async_db
from app.models.products import Product as ProductModel
from app.models.categories import Category as CategoryModel
from app.models.users import User as UserModel
from app.auth import get_current_seller

router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", response_model=ProductList, status_code=status.HTTP_200_OK)
async def get_all_products(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1,  le=100),
        category_id: int | None = Query(None, description="ID of category for filter"),
        min_price: float | None = Query(None, ge=0, description="Minimal price"),
        max_price: float | None = Query(None, ge=0, description="Maximal price"),
        in_stock: bool | None = Query(None, description="An availability in stock"),
        seller_id: int | None = Query(None, description="Id seller"),
        db: AsyncSession = Depends(get_async_db)
):
    if (min_price is not None) and (max_price is not None) and (min_price > max_price):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price couldn't be higher than max_price"
        )

    filters = [ProductModel.is_active == True]

    if category_id is not None:
        filters.append(ProductModel.category_id == category_id)
    if min_price is not None:
        filters.append(ProductModel.price >= category_id)
    if max_price is not None:
        filters.append(ProductModel.price <= max_price)
    if in_stock is not None:
        filters.append(ProductModel.stock > 0 if in_stock else ProductModel.stock == 0)
    if seller_id is not None:
        filters.append(ProductModel.seller_id == seller_id)

    # Подсчёт общего количества с учётом фильтров
    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)
    total = await db.scalar(total_stmt) or 0

    # Выборка товаров с фильтрами и пагинацией
    products_stmt = (
        select(ProductModel)
        .where(*filters)
        .order_by(ProductModel.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.scalars(products_stmt)).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate,
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    stmt = select(CategoryModel).where(CategoryModel.id == product.category_id,
                                         CategoryModel.is_active == True)
    temp = await db.scalars(stmt)
    cat = temp.first()
    if cat:
        db_product = ProductModel(**product.model_dump(), seller_id=current_user.id)
        db.add(db_product)
        await db.commit()
        await db.refresh(db_product)
        return db_product
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")


@router.get("/category/{category_id}", response_model=list[ProductSchema], status_code=status.HTTP_200_OK)
async def get_products_by_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.id == category_id,
                                       CategoryModel.is_active == True)
    temp = await db.scalars(stmt)
    cat = temp.first()
    if cat is not None:
        temp = await db.scalars(select(ProductModel).where(ProductModel.is_active == True,
                                                            ProductModel.category_id == category_id))
        products = temp.all()
        return products
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found or inactive")


@router.get("/{product_id}", response_model= ProductSchema, status_code=status.HTTP_200_OK)
async def get_product(product_id: int,  db: AsyncSession = Depends(get_async_db)):
    stmt = select(ProductModel).where(ProductModel.id == product_id,
                                      ProductModel.is_active == True)
    temp = await db.scalars(stmt)
    product = temp.first()
    if product:
        category_result = await db.scalars(select(CategoryModel).where(CategoryModel.id == product.category_id,
                                                                       CategoryModel.is_active == True))
        category = category_result.first()
        if category:
            return product
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found or inactive')
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")


@router.put("/{product_id}", response_model=ProductSchema,  status_code=status.HTTP_200_OK)
async def update_product(
        product_id: int,
        body_product: ProductCreate,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_seller)):
    """
    Obtain available product
    """
    pre_product = await db.scalars(select(ProductModel).where(ProductModel.id == product_id,
                                                                          ProductModel.is_active == True))
    product = pre_product.first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    """
        Check product's owner
    """
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own products")
    """
        Check product's category
    """
    pre_category = await db.scalars(
        select(CategoryModel).where(CategoryModel.id == product.category_id,
                                                CategoryModel.is_active == True))
    category = pre_category.first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")
    """
        Update product
    """
    await db.execute(
        update(ProductModel).where(ProductModel.id == product_id).values(**body_product.model_dump())
    )
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", response_model=ProductSchema, status_code=status.HTTP_200_OK)
async def delete_product(product_id: int,
                         db: AsyncSession = Depends(get_async_db),
                         current_user: UserModel = Depends(get_current_seller)):
    pre_product = await db.scalars(select(ProductModel).where(ProductModel.id == product_id,
                                                              ProductModel.is_active == True))
    """
        Check available product
    """
    product = pre_product.first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    """
        Check product's owner
    """
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own products")
    """
        Delete product
    """
    await db.execute(update(ProductModel).where(ProductModel.id == product_id).values(is_active=False))
    await db.commit()
    await db.refresh(product)
    return product
