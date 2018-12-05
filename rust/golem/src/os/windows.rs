use std::mem::size_of;
use winapi::shared::minwindef::DWORD;
use winapi::shared::minwindef::LPDWORD;
use winapi::shared::ntdef::FALSE;
use winapi::shared::ntdef::NULL;
use winapi::um::processthreadsapi::OpenProcess;
use winapi::um::psapi::EmptyWorkingSet;
use winapi::um::psapi::EnumProcesses;
use winapi::um::winnt::PROCESS_ALL_ACCESS;
use winapi::um::winnt::PROCESS_QUERY_INFORMATION;
use winapi::um::winnt::PROCESS_VM_READ;
use winapi::shared::ntdef::HANDLE;
use os::error::OSError;

const MAX_PROCESS_COUNT: usize = 2048;


struct Processes {
    array: [u32; MAX_PROCESS_COUNT],
    count: DWORD,
}

impl Processes {
    pub fn new() -> Self {
        Processes {
            array: [0; MAX_PROCESS_COUNT],
            count: 0,
        }
    }

    #[cfg(windows)]
    pub fn enumerate(&mut self) -> Result<(), OSError> {
        // A pointer to an array that receives the list of process identifiers
        let lpid_process = &mut self.array[0];
        // The size of the pProcessIds array, in bytes
        let cb: DWORD = (size_of::<DWORD>() * MAX_PROCESS_COUNT) as DWORD;
        // The number of bytes returned in the pProcessIds array
        let mut cb_needed: DWORD = 0;
        // A pointer to the number of bytes returned
        let lpcb_needed: LPDWORD = &mut cb_needed;

        unsafe {
            if EnumProcesses(lpid_process, cb, lpcb_needed) == 0 {
                return Err(OSError::new("Unable to enumerate processes"));
            }

            self.count = (*lpcb_needed) / size_of::<DWORD>() as u32;
        }

        Ok(())
    }

    #[cfg(windows)]
    pub fn open(&self, idx: usize) -> HANDLE {
        let id = self.array[idx];
        if id == 0 {
            return NULL;
        }

        unsafe {
            OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_ALL_ACCESS,
                FALSE as i32,
                id,
            )
        }
    }
}


#[cfg(windows)]
pub fn empty_working_sets() -> Result<(), OSError> {
    let mut processes = Processes::new();
    processes.enumerate()?;

    for idx in 0..processes.count as usize {
        let handle = processes.open(idx);

        if handle != NULL {
            unsafe {
                EmptyWorkingSet(handle);
            }
        }
    }

    Ok(())
}

#[cfg(not(windows))]
pub fn empty_working_sets() -> Result<(), OSError> {
    Err(OSError::new("Unsupported OS"))
}
