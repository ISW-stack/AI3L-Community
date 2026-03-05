export interface Contributor {
  id: string
  github_username: string
  display_name: string
  role: string
  display_order: number
  avatar_url: string
}

export interface ContributorCreate {
  github_username: string
  display_name: string
  role: string
  display_order?: number
}

export interface ContributorUpdate {
  github_username?: string
  display_name?: string
  role?: string
  display_order?: number
}
