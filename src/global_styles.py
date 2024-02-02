

DEFAULT_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        width: 10px;
        background-color: #CCCCCC;
    }
    
    QScrollBar::handle:vertical {
        min-height: 30px;
        background-color: #666666;
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