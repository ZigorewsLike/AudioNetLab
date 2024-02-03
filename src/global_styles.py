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
        width: 10px;
        background-color: """ + AppColorSchemes.SCROLLBAR_BACKGROUND + """;
    }
    
    QScrollBar::handle:vertical {
        min-height: 30px;
        width: 8px;
        margin: 1px;
        margin-top: 2px;
        border-radius: 2px;
        background-color: """ + AppColorSchemes.SCROLLBAR_BODY + """;
    }
    
    QScrollBar::add-line:vertical {
        background: none;
        height: 10px;
        subcontrol-position: bottom;
        subcontrol-origin: margin;
    }
    
    QScrollBar::sub-line:vertical {
        background: none;
        height: 45px;
        subcontrol-position: top;
        subcontrol-origin: margin;
    }
    
    QScrollBar::up-arrow:vertical { 
        -image:url('./icons/up_48.png'); 
        height: 10px; 
        width: 10px 
    }
    
    QScrollBar::down-arrow:vertical {
        -image:url('./icons/down_48.png'); 
        height: 10px; 
        width: 10px                              
    }
"""