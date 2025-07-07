#!/usr/bin/env python3
"""
Progress indicators and performance monitoring for Basher.
"""

import time
import threading
import functools


def timing_decorator(func):
    """Decorator to measure function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"⧖ {func.__name__} took {end-start:.2f}s")
        return result
    return wrapper


class ProgressIndicator:
    """Dynamic progress indicator that updates in place"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.current_message = ""
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_index = 0
        self.spinning = False
        self.spinner_thread = None
        self.stop_event = threading.Event()
    
    def update(self, message: str, clear_previous: bool = True):
        """Update progress message, optionally clearing previous line"""
        if not self.enabled:
            return
        
        if clear_previous and self.current_message:
            # Clear the current line
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
        
        self.current_message = message
        print(f"\r{message}", end='', flush=True)
    
    def start_spinner(self, message: str):
        """Start continuous spinner animation"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any existing spinner
        self.current_message = message
        self.spinning = True
        self.stop_event.clear()
        self.spinner_thread = threading.Thread(target=self._animate_spinner)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop_spinner(self):
        """Stop the spinner animation"""
        if self.spinner_thread and self.spinning:
            self.spinning = False
            self.stop_event.set()
            self.spinner_thread.join(timeout=0.5)
            self.spinner_thread = None
    
    def _animate_spinner(self):
        """Internal method to animate the spinner"""
        while self.spinning and not self.stop_event.is_set():
            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            self.spinner_index += 1
            full_message = f"{spinner} {self.current_message}"
            
            # Clear and update the line
            print(f"\r{' ' * 80}\r{full_message}", end='', flush=True)
            
            if self.stop_event.wait(0.1):  # 100ms delay between frames
                break
    
    def update_with_spinner(self, message: str):
        """Update with animated spinner (legacy method for compatibility)"""
        if not self.enabled:
            return
        
        spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
        self.spinner_index += 1
        full_message = f"{spinner} {message}"
        
        if self.current_message:
            # Clear the current line
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
        
        self.current_message = full_message
        print(f"\r{full_message}", end='', flush=True)
    
    def complete(self, final_message: str = None):
        """Complete progress and optionally show final message"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any running spinner
        
        # Clear the current line more thoroughly
        print(f"\r{' ' * 80}\r", end='', flush=True)
        
        if final_message:
            print(final_message)
        
        self.current_message = ""
    
    def clear(self):
        """Clear current progress line"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any running spinner
        
        if self.current_message:
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
            self.current_message = ""