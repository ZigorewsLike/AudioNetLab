from enum import Enum


class AppColorSchemes(str, Enum):
    SCROLLBAR_BODY = "#666666"
    FILE_LIST_BACKGROUND = "#B3B3B3"
    SCROLLBAR_BACKGROUND = "#CCCCCC"
    FILE_LIST_ITEM_BODY = "#D9D9D9"
    BUTTON_HOVER = "#E6E6E6"

    # Invert colors
    # SCROLLBAR_BODY = "#999999"
    # FILE_LIST_BACKGROUND = "#4c4c4c"
    # SCROLLBAR_BACKGROUND = "#333333"
    # FILE_LIST_ITEM_BODY = "#262626"
    # BUTTON_HOVER = "#191919"


DEFAULT_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        width: 12px;
        background-color: """ + AppColorSchemes.SCROLLBAR_BACKGROUND + """;
    }
    
    QScrollBar::handle:vertical {
        min-height: 30px;
        width: 6px;
        margin: 3px;
        margin-top: 2px;
        border-radius: 2px;
        background-color: """ + AppColorSchemes.SCROLLBAR_BODY + """;
    }
    
    QScrollBar::handle:vertical:pressed {
        width: 8px;
        margin: 2px;
    }
    
    QScrollBar::add-line:vertical {
        background: none;
        height: 0px;
    }
    
    QScrollBar::sub-line:vertical {
        background: none;
        height: 0px;
    }
    
    QScrollBar::up-arrow:vertical { 
        height: 0px; 
        width: 0px 
    }
    
    QScrollBar::down-arrow:vertical {
        height: 0px; 
        width: 0px                              
    }
"""