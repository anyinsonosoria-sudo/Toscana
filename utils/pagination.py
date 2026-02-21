"""
Pagination Helper
=================
Helper para paginación consistente en toda la aplicación.
"""

from flask import request
from math import ceil


class Pagination:
    """
    Clase helper para manejar paginación de resultados.
    
    Uso:
        items = get_all_items()
        pagination = Pagination(items, page=1, per_page=20)
        
        # En template:
        for item in pagination.items:
            ...
        
        # Información de paginación:
        pagination.page       # Página actual
        pagination.pages      # Total de páginas
        pagination.has_prev   # ¿Hay página anterior?
        pagination.has_next   # ¿Hay página siguiente?
        pagination.prev_num   # Número de página anterior
        pagination.next_num   # Número de página siguiente
    """
    
    def __init__(self, items, page=1, per_page=20):
        """
        Inicializa paginación.
        
        Args:
            items: Lista completa de items
            page: Número de página (1-indexed)
            per_page: Items por página
        """
        self.items = items
        self.page = max(1, page)
        self.per_page = per_page
        self.total = len(items)
        self.pages = ceil(self.total / per_page) if per_page > 0 else 0
        
        # Validar que la página no exceda el total
        if self.pages > 0 and self.page > self.pages:
            self.page = self.pages
        
        # Calcular indices para slicing
        start = (self.page - 1) * per_page
        end = start + per_page
        
        # Items de la página actual
        self.items = items[start:end]
    
    @property
    def has_prev(self):
        """¿Hay página anterior?"""
        return self.page > 1
    
    @property
    def has_next(self):
        """¿Hay página siguiente?"""
        return self.page < self.pages
    
    @property
    def prev_num(self):
        """Número de página anterior"""
        return self.page - 1 if self.has_prev else None
    
    @property
    def next_num(self):
        """Número de página siguiente"""
        return self.page + 1 if self.has_next else None
    
    def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
        """
        Genera números de página para navegación.
        
        Ejemplo: [1, 2, None, 8, 9, 10, 11, 12, None, 49, 50]
        Donde None representa "..."
        
        Args:
            left_edge: Páginas al inicio
            left_current: Páginas antes de la actual
            right_current: Páginas después de la actual
            right_edge: Páginas al final
        """
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (self.page - left_current <= num <= self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


def paginate(items, per_page=20):
    """
    Helper function para paginar items desde request args.
    
    Uso en route:
        @app.route('/items')
        def list_items():
            all_items = get_all_items()
            pagination = paginate(all_items, per_page=20)
            return render_template('items.html', pagination=pagination)
    
    Args:
        items: Lista de items a paginar
        per_page: Items por página (default: 20)
    
    Returns:
        Pagination object
    """
    # Obtener página de query string
    page = request.args.get('page', 1, type=int)
    
    return Pagination(items, page=page, per_page=per_page)


def get_page_range(current_page, total_pages, max_visible=7):
    """
    Calcula el rango de páginas a mostrar en la navegación.
    
    Ejemplos:
        - Página 1 de 10 con max 7: [1, 2, 3, 4, 5, ..., 10]
        - Página 5 de 10 con max 7: [1, ..., 3, 4, 5, 6, 7, ..., 10]
        - Página 10 de 10 con max 7: [1, ..., 6, 7, 8, 9, 10]
    
    Args:
        current_page: Página actual
        total_pages: Total de páginas
        max_visible: Máximo de páginas visibles
    
    Returns:
        Lista de números o None (para "...")
    """
    if total_pages <= max_visible:
        return list(range(1, total_pages + 1))
    
    pages = []
    
    # Siempre mostrar primera página
    pages.append(1)
    
    # Calcular rango alrededor de la página actual
    half = max_visible // 2
    start = max(2, current_page - half)
    end = min(total_pages - 1, current_page + half)
    
    # Ajustar si estamos cerca del inicio o final
    if current_page <= half:
        end = max_visible - 1
    elif current_page >= total_pages - half:
        start = total_pages - max_visible + 2
    
    # Agregar "..." si hay gap
    if start > 2:
        pages.append(None)
    
    # Agregar páginas del rango
    pages.extend(range(start, end + 1))
    
    # Agregar "..." si hay gap
    if end < total_pages - 1:
        pages.append(None)
    
    # Siempre mostrar última página
    if total_pages > 1:
        pages.append(total_pages)
    
    return pages
