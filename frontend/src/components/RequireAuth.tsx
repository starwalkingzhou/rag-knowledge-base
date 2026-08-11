import {Spin} from 'antd'
import {Navigate, Outlet, useLocation} from 'react-router-dom'
import {useQuery} from '@tanstack/react-query'
import {fetchCurrentUser} from '@/api/auth'
import {currentUserKey} from '@/api/queryKeys'
import {useAuthStore} from '@/store/authStore'

export function RequireAuth() {
    const location = useLocation()
    const ready = useAuthStore(s => s.ready)
    const token = useAuthStore(s => s.token)
    const setUser = useAuthStore(s => s.setUser)

    const {data: freshUser} = useQuery({
        queryKey: currentUserKey,
        queryFn: fetchCurrentUser,
        enabled: ready && Boolean(token),
        staleTime: 60_000,
        retry: false,
    })

    if (!ready) {
        return (
            <div style={{minHeight: '100vh', display: 'grid', placeItems: 'center'}}>
                <Spin/>
            </div>
        )
    }

    if (!token) {
        const back = encodeURIComponent(location.pathname + location.search)
        return <Navigate to={`/login?back=${back}`} replace/>
    }

    if (freshUser) {
        setUser(freshUser)
    }

    return <Outlet/>
}
